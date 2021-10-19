#!/usr/bin/env python3
"""SlurmctldCharm."""
import copy
import logging
import shlex
import subprocess
from pathlib import Path
from typing import List

from ops.charm import CharmBase, LeaderElectedEvent
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, ModelError, WaitingStatus

from etcd_ops import EtcdOps
from interface_grafana_source import GrafanaSource
from interface_influxdb import InfluxDB
from interface_slurmctld_peer import SlurmctldPeer
from interface_slurmd import Slurmd
from interface_slurmdbd import Slurmdbd
from interface_slurmrestd import Slurmrestd
from interface_user_group import UserGroupRequires
from slurm_ops_manager import SlurmManager

from charms.fluentbit.v0.fluentbit import FluentbitClient

logger = logging.getLogger()


class SlurmctldCharm(CharmBase):
    """Slurmctld lifecycle events."""

    _stored = StoredState()

    def __init__(self, *args):
        """Init _stored attributes and interfaces, observe events."""
        super().__init__(*args)

        self._stored.set_default(
            jwt_key=str(),
            munge_key=str(),
            slurm_installed=False,
            slurmd_available=False,
            slurmrestd_available=False,
            slurmdbd_available=False,
            down_nodes=list(),
        )

        self._slurm_manager = SlurmManager(self, "slurmctld")
        self._user_group = UserGroupRequires(self, "user-group")

        self._fluentbit = FluentbitClient(self, "fluentbit")

        self._slurmd = Slurmd(self, "slurmd")
        self._slurmdbd = Slurmdbd(self, "slurmdbd")
        self._slurmrestd = Slurmrestd(self, "slurmrestd")
        self._slurmctld_peer = SlurmctldPeer(self, "slurmctld-peer")

        self._grafana = GrafanaSource(self, "grafana-source")
        self._influxdb = InfluxDB(self, "influxdb-api")

        self._etcd = EtcdOps()

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.upgrade_charm: self._on_upgrade,
            self.on.update_status: self._on_update_status,
            self.on.config_changed: self._on_write_slurm_config,
            self.on.leader_elected: self._on_leader_elected,
            # slurm component lifecycle events
            self._slurmdbd.on.slurmdbd_available: self._on_slurmdbd_available,
            self._slurmdbd.on.slurmdbd_unavailable: self._on_slurmdbd_unavailable,
            self._slurmd.on.slurmd_available: self._on_write_slurm_config,
            self._slurmd.on.slurmd_unavailable: self._on_write_slurm_config,
            self._slurmd.on.slurmd_departed: self._on_write_slurm_config,
            self._slurmrestd.on.slurmrestd_available: self._on_slurmrestd_available,
            self._slurmrestd.on.slurmrestd_unavailable: self._on_write_slurm_config,
            self._slurmctld_peer.on.slurmctld_peer_available: self._on_write_slurm_config, # NOTE: a second slurmctld should get the jwt/munge keys and configure them
            # fluentbit
            self.on["fluentbit"].relation_created: self._on_fluentbit_relation_created,
            # Addons lifecycle events
            self._grafana.on.grafana_available: self._on_grafana_available,
            self._influxdb.on.influxdb_available: self._on_influxdb_available,
            self._influxdb.on.influxdb_unavailable: self._on_write_slurm_config,
            self._user_group.on.create_user_group: self._on_create_user_group,
            self._user_group.on.remove_user_group: self._on_remove_user_group,
            # actions
            self.on.show_current_config_action: self._on_show_current_config,
            self.on.drain_action: self._drain_nodes_action,
            self.on.resume_action: self._resume_nodes_action,
            self.on.influxdb_info_action: self._infludb_info_action,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    @property
    def hostname(self):
        """Return the hostname."""
        return self._slurm_manager.hostname

    @property
    def port(self):
        """Return the port."""
        return self._slurm_manager.port

    @property
    def _slurmctld_info(self):
        return self._slurmctld_peer.get_slurmctld_info()

    @property
    def slurmdbd_info(self):
        """Return slurmdbd_info from relation."""
        return self._slurmdbd.get_slurmdbd_info()

    @property
    def _slurmd_info(self) -> list:
        return self._slurmd.get_slurmd_info()

    @property
    def _cluster_info(self):
        """Assemble information about the cluster."""
        cluster_info = {}
        cluster_info['cluster_name'] = self.config.get('cluster-name')
        cluster_info['custom_config'] = self.config.get('custom-config')
        cluster_info['proctrack_type'] = self.config.get('proctrack-type')
        cluster_info['cgroup_config'] = self.config.get('cgroup-config')

        interval = self.config.get('health-check-interval')
        state = self.config.get('health-check-state')
        nhc = self._slurm_manager.slurm_config_nhc_values(interval, state)
        cluster_info.update(nhc)

        return cluster_info

    @property
    def _addons_info(self):
        """Assemble addons for slurm.conf."""
        # NOTE add prolog and epilog
        # NOTE add elasticsearch

        return {**self._assemble_acct_gather_addons()}

    def _assemble_acct_gather_addons(self):
        """Generate the acct gather section of the addons."""
        addons = dict()

        influxdb_info = self._get_influxdb_info()
        if influxdb_info:
            addons["acct_gather"] = influxdb_info
            addons["acct_gather"]["default"] = "all"
            addons["acct_gather_profile"] = "acct_gather_profile/influxdb"

        # it is possible to setup influxdb or hdf5 profiles without the
        # relation, using the custom-config section of slurm.conf. We need to
        # support setting up the acct_gather configuration for this scenario
        acct_gather_custom = self.config.get("acct-gather-custom")
        if acct_gather_custom:
            if not addons.get("acct_gather"):
                addons["acct_gather"] = dict()

            addons["acct_gather"]["custom"] = acct_gather_custom

        addons["acct_gather_frequency"] = self.config.get("acct-gather-frequency")

        return addons

    def set_slurmd_available(self, flag: bool):
        """Set stored value of slurmd available."""
        self._stored.slurmd_available = flag

    def _set_slurmdbd_available(self, flag: bool):
        """Set stored value of slurmdbd available."""
        self._stored.slurmdbd_available = flag

    def set_slurmrestd_available(self, flag: bool):
        """Set stored value of slurmdrest available."""
        self._stored.slurmrestd_available = flag

    def _is_leader(self):
        return self.model.unit.is_leader()

    def is_slurm_installed(self):
        """Return true/false based on whether or not slurm is installed."""
        return self._stored.slurm_installed

    def _on_show_current_config(self, event):
        """Show current slurm.conf."""
        slurm_conf = self._slurm_manager.get_slurm_conf()
        event.set_results({"slurm.conf": slurm_conf})

    def _on_install(self, event):
        """Perform installation operations for slurmctld."""
        self.unit.set_workload_version(Path("version").read_text().strip())

        self.unit.status = WaitingStatus("Installing slurmctld")

        custom_repo = self.config.get("custom-slurm-repo")
        successful_installation = self._slurm_manager.install(custom_repo)

        if successful_installation:
            self._stored.slurm_installed = True

            # Store the munge_key and jwt_rsa key in the stored state.
            # NOTE: Use leadership settings instead of stored state when
            # leadership settings support becomes available in the framework.
            if self._is_leader():
                # NOTE the backup controller should also have the jwt and munge
                #      keys configured. We should move these information to the
                #      peer relation.
                self._stored.jwt_rsa = self._slurm_manager.generate_jwt_rsa()
                self._stored.munge_key = self._slurm_manager.get_munge_key()
                self._slurm_manager.configure_jwt_rsa(self.get_jwt_rsa())
            else:
                # NOTE: the secondary slurmctld should get the jwt and munge
                #       keys from the peer relation here
                logger.debug("secondary slurmctld")

            # all slurmctld should restart munged here, as it would assure
            # munge is working
            self._slurm_manager.restart_munged()
        else:
            self.unit.status = BlockedStatus("Error installing slurmctld")
            event.defer()

        logger.debug("## Retrieving etcd resource to install it")
        try:
            etcd_path = self.model.resources.fetch("etcd")
            logger.debug(f"## Found etcd resource: {etcd_path}")
        except ModelError:
            logger.error("## Missing etcd resource")
            self.unit.status = BlockedStatus("Missing etcd resource")
            event.defer()
            return
        self._etcd.install(etcd_path)

        self._check_status()

    def _on_fluentbit_relation_created(self, event):
        """Set up Fluentbit log forwarding."""
        logger.debug("## Configuring fluentbit")
        cfg = list()
        cfg.extend(self._slurm_manager.fluentbit_config_nhc)
        cfg.extend(self._slurm_manager.fluentbit_config_slurm)
        self._fluentbit.configure(cfg)

    def _on_upgrade(self, event):
        """Perform upgrade operations."""
        self.unit.set_workload_version(Path("version").read_text().strip())

    def _on_update_status(self, event):
        """Handle update status."""
        self._check_status()

    def _on_leader_elected(self, event: LeaderElectedEvent) -> None:
        logger.debug("## slurmctld - leader elected")
        self._etcd.start()

        # populate etcd with the nodelist
        slurm_config = self._assemble_slurm_config()
        accounted_nodes = self._assemble_all_nodes(slurm_config.get("partitions", []))
        logger.debug(f"## Sending to etcd list of accounted nodes: {accounted_nodes}")
        self._etcd.set_list_of_accounted_nodes(accounted_nodes)

    def _check_status(self):
        """Check for all relations and set appropriate status.

        This charm needs these conditions to be satified in order to be ready:
        - Slurm components installed.
        - Munge running.
        - slurmdbd node running.
        - slurmd inventory.
        """
        # NOTE: slurmd and slurmrestd are not needed for slurmctld to work,
        #       only for the cluster to operate. But we need slurmd inventory
        #       to assemble slurm.conf

        if not self._stored.slurm_installed:
            self.unit.stauts = BlockedStatus("Error installing slurmctld")
            return False

        if (self._is_leader() and not self._etcd.is_active()):
            self.unit.stauts = WaitingStatus("Initializing charm")
            return False

        if not self._slurm_manager.check_munged():
            self.unit.stauts = BlockedStatus("Error configuring munge key")
            return False

        # statuses of mandatory components:
        # - joined: someone executed juju relate slurmctld foo
        # - available: the units exchanged data through the relation
        # NOTE: slurmrestd is not mandatory for the cluster to work, that's why
        #       it is not acounted for in here
        statuses = {"slurmd": {"available": self._stored.slurmd_available,
                               "joined": self._slurmd.is_joined},
                    "slurmdbd": {"available": self._stored.slurmdbd_available,
                                 "joined": self._slurmdbd.is_joined}}

        relations_needed = list()
        waiting_on = list()
        for component in statuses.keys():
            if not statuses[component]["joined"]:
                relations_needed.append(component)
            if not statuses[component]["available"]:
                waiting_on.append(component)

        if len(relations_needed):
            msg = f"Need relations: {','.join(relations_needed)}"
            self.unit.status = BlockedStatus(msg)
            return False

        if len(waiting_on):
            msg = f"Wating on: {','.join(waiting_on)}"
            self.unit.status = WaitingStatus(msg)
            return False

        self.unit.status = ActiveStatus("slurmctld available")
        return True

    def get_munge_key(self):
        """Get the stored munge key."""
        return self._stored.munge_key

    def get_jwt_rsa(self):
        """Get the stored jwt_rsa key."""
        return self._stored.jwt_rsa

    def _assemble_partitions(self, slurmd_info):
        """Make any needed modifications to partition data."""
        slurmd_info_tmp = copy.deepcopy(slurmd_info)
        default_partition_from_config = self.config.get("default-partition")

        for partition in slurmd_info:
            # Deep copy the partition to a tmp var so we can modify it as
            # needed whilst not modifying the object we are iterating over.
            partition_tmp = copy.deepcopy(partition)
            # Extract the partition_name from the partition.
            partition_name = partition["partition_name"]

            # Check that the default_partition isn't defined in the charm
            # config.
            # If the user hasn't provided a default partition, then we infer
            # the partition_default by defaulting to the "configurator"
            # partition.
            if default_partition_from_config:
                if default_partition_from_config == partition_name:
                    partition_tmp["partition_default"] = "YES"

            slurmd_info_tmp.remove(partition)
            slurmd_info_tmp.append(partition_tmp)

        return slurmd_info_tmp

    def _assemble_slurm_config(self):
        """Assemble and return the slurm config."""
        logger.debug('## Assembling new slurm.conf')

        slurmctld_info = self._slurmctld_info
        slurmdbd_info = self.slurmdbd_info
        slurmd_info = self._slurmd_info
        cluster_info = self._cluster_info

        logger.debug("######## INFO")
        logger.debug(f'## slurmd: {slurmd_info}')
        logger.debug(f'## slurmctld_info: {slurmctld_info}')
        logger.debug(f'## slurmdbd_info: {slurmdbd_info}')
        logger.debug(f'## cluster_info: {cluster_info}')
        logger.debug("######## INFO - end")

        if not (slurmctld_info and slurmd_info and slurmdbd_info):
            return {}

        addons_info = self._addons_info
        partitions_info = self._assemble_partitions(slurmd_info)
        down_nodes = self._assemble_down_nodes(slurmd_info)

        logger.debug(f'#### addons: {addons_info}')
        logger.debug(f'#### partitions_info: {partitions_info}')
        logger.debug(f"#### Down nodes: {down_nodes}")

        return {
            "partitions": partitions_info,
            "down_nodes": down_nodes,
            **slurmctld_info,
            **slurmdbd_info,
            **addons_info,
            **cluster_info,
        }

    def _on_slurmrestd_available(self, event):
        """Set slurm_config on the relation when slurmrestd available."""
        if not self._check_status():
            event.defer()
            return

        slurm_config = self._assemble_slurm_config()

        if not slurm_config:
            self.unit.status = BlockedStatus(
                "Cannot generate slurm_config - defering event."
            )
            event.defer()
            return

        if self._stored.slurmrestd_available:
            self._slurmrestd.set_slurm_config_on_app_relation_data(
                slurm_config,
            )
            self._slurmrestd.restart_slurmrestd()

    def _on_slurmdbd_available(self, event):
        self._set_slurmdbd_available(True)
        self._on_write_slurm_config(event)

    def _on_slurmdbd_unavailable(self, event):
        self._set_slurmdbd_available(False)
        self._check_status()

    def _on_write_slurm_config(self, event):
        """Check that we have what we need before we proceed."""
        logger.debug("### Slurmctld - _on_write_slurm_config()")

        # only the leader should write the config, restart, and scontrol reconf
        if not self._is_leader():
            return

        if not self._check_status():
            event.defer()
            return

        slurm_config = self._assemble_slurm_config()
        if slurm_config:
            self._slurm_manager.render_slurm_configs(slurm_config)

            # restart is needed if nodes are added/removed from the cluster
            self._slurm_manager.slurm_systemctl('restart')
            self._slurm_manager.slurm_cmd('scontrol', 'reconfigure')

            # send the list of hostnames to slurmd relation data
            accounted_nodes = self._assemble_all_nodes(slurm_config["partitions"])
            self._etcd.set_list_of_accounted_nodes(accounted_nodes)

            # check for "not new anymore" nodes, i.e., nodes that runned the
            # node-configured action. Those nodes are not anymore in the
            # DownNodes section in the slurm.conf, but we need to resume them
            # manually and update the internal cache
            down_nodes = slurm_config['down_nodes']
            configured_nodes = self._assemble_configured_nodes(down_nodes)
            logger.debug(f"### configured nodes: {configured_nodes}")
            self._resume_nodes(configured_nodes)
            self._stored.down_nodes = down_nodes.copy()

            # slurmrestd needs the slurm.conf file, so send it every time it changes
            if self._stored.slurmrestd_available:
                self._slurmrestd.set_slurm_config_on_app_relation_data(slurm_config)
                # NOTE: scontrol reconfigure does not restart slurmrestd
                self._slurmrestd.restart_slurmrestd()
        else:
            logger.debug("## Should rewrite slurm.conf, but we don't have it. "
                         "Deferring.")
            event.defer()

    @staticmethod
    def _assemble_all_nodes(slurmd_info: list) -> List[str]:
        """Parse slurmd_info and return a list with all hostnames."""
        nodes = list()
        for partition in slurmd_info:
            for node in partition["inventory"]:
                nodes.append(node["node_name"])
        return nodes

    @staticmethod
    def _assemble_down_nodes(slurmd_info):
        """Parse partitions' nodes and assemble a list of DownNodes."""
        down_nodes = []
        for partition in slurmd_info:
            for node in partition["inventory"]:
                if node["new_node"]:
                    down_nodes.append(node["node_name"])

        return down_nodes

    def _assemble_configured_nodes(self, down_nodes):
        """Assemble list of nodes that are not new anymore.

        new_node status is removed with an action, this method returns a list
        of nodes that were previously new but are not anymore.
        """
        configured_nodes = []
        for node in self._stored.down_nodes:
            if node not in down_nodes:
                configured_nodes.append(node)

        return configured_nodes

    def _resume_nodes(self, nodelist):
        """Run scontrol to resume the speficied node list."""
        nodes = ",".join(nodelist)
        update_cmd = f"update nodename={nodes} state=resume"
        self._slurm_manager.slurm_cmd('scontrol', update_cmd)

    def _on_grafana_available(self, event):
        """Create the grafana-source if we are the leader and have influxdb."""
        if not self._is_leader():
            return

        influxdb_info = self._get_influxdb_info()

        if influxdb_info:
            self._grafana.set_grafana_source_info(influxdb_info)
        else:
            logger.error("## Can not set Grafana source: missing influxdb relation")

    def _on_influxdb_available(self, event):
        """Assemble addons to forward slurm data to influxdb."""
        self._on_write_slurm_config(event)

    def _get_influxdb_info(self) -> dict:
        """Return influxdb info."""
        return self._influxdb.get_influxdb_info()

    def _drain_nodes_action(self, event):
        """Drain specified nodes."""
        nodes = event.params['nodename']
        reason = event.params['reason']

        logger.debug(f'#### Draining {nodes} because {reason}.')
        event.log(f'Draining {nodes} because {reason}.')

        try:
            cmd = f'scontrol update nodename={nodes} state=drain reason="{reason}"'
            subprocess.check_output(shlex.split(cmd))
            event.set_results({'status': 'draining', 'nodes': nodes})
        except subprocess.CalledProcessError as e:
            event.fail(message=f'Error draining {nodes}: {e.output}')

    def _resume_nodes_action(self, event):
        """Resume specified nodes."""
        nodes = event.params['nodename']

        logger.debug(f'#### Resuming {nodes}.')
        event.log(f'Resuming {nodes}.')

        try:
            cmd = f'scontrol update nodename={nodes} state=resume'
            subprocess.check_output(shlex.split(cmd))
            event.set_results({'status': 'resuming', 'nodes': nodes})
        except subprocess.CalledProcessError as e:
            event.fail(message=f'Error resuming {nodes}: {e.output}')

    def _infludb_info_action(self, event):
        influxdb_info = self._get_influxdb_info()

        if not influxdb_info:
            influxdb_info = "not related"
        logger.debug(f"## InfluxDB-info action: {influxdb_info}")
        event.set_results({"influxdb": influxdb_info})

    def _on_create_user_group(self, event):
        """Create the user and group provided."""
        user = self._user_group._user_name
        user_uid = self._user_group._user_uid
        group = self._user_group._group_name

        # Create the group.
        try:
            subprocess.check_output(["groupadd", group])
        except subprocess.CalledProcessError as e:
            if e.returncode == 9:
                logger.warning("## Group already exists.")
            else:
                logger.error(f"## Error creating group: {e}")

        # Create the user.
        try:
            subprocess.check_output(
                [
                    "useradd",
                    "--system",
                    "--no-create-home",
                    "--gid",
                    group,
                    "--shell",
                    "/usr/sbin/nologin",
                    "-u",
                    user_uid,
                    user,
                ]
            )
        except subprocess.CalledProcessError as e:
            if e.returncode == 9:
                logger.warning("## User already exists.")
            else:
                logger.error(f"## Error creating user: {e}")

    def _on_remove_user_group(self, event):
        """Remove the user and group provided."""
        user = self._user_group._user_name
        group = self._user_group._group_name

        # Remove the user.
        try:
            subprocess.check_output(
                [
                    "userdel",
                    user,
                ]
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"## Error deleting user: {e}")

        # Remove the group.
        try:
            subprocess.check_output(["groupdel", group])
        except subprocess.CalledProcessError as e:
            logger.error(f"## Error deleting group: {e}")


if __name__ == "__main__":
    main(SlurmctldCharm)
