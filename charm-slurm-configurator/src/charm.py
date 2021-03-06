#!/usr/bin/env python3
"""SlurmConfiguratorCharm."""
import copy
import logging
import uuid

from interface_elasticsearch import Elasticsearch
from interface_grafana_source import GrafanaSource
from interface_influxdb import InfluxDB
from interface_prolog_epilog import PrologEpilog
from interface_slurmctld import Slurmctld
from interface_slurmdbd import Slurmdbd
from interface_slurmrestd import Slurmrestd
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from slurm_ops_manager import SlurmManager

from interface_slurmd import Slurmd

logger = logging.getLogger()


class SlurmConfiguratorCharm(CharmBase):
    """Facilitate slurm configuration operations."""

    _stored = StoredState()

    def __init__(self, *args):
        """Init charm, _stored defaults, interfaces and observe events."""
        super().__init__(*args)

        self._stored.set_default(
            munge_key=str(),
            jwt_rsa=str(),
            slurm_installed=False,
            slurmd_restarted=False,
            slurmctld_available=False,
            slurmdbd_available=False,
            slurmd_available=False,
            slurmrestd_available=False,
            down_nodes=list(),
            force_reconfiguration=False,
        )

        self._elasticsearch = Elasticsearch(self, "elasticsearch")
        self._grafana = GrafanaSource(self, "grafana-source")
        self._influxdb = InfluxDB(self, "influxdb-api")
        self._slurmrestd = Slurmrestd(self, "slurmrestd")
        self._slurm_manager = SlurmManager(self, "slurmd")
        self._slurmctld = Slurmctld(self, "slurmctld")
        self._slurmdbd = Slurmdbd(self, "slurmdbd")
        self._slurmd = Slurmd(self, "slurmd")
        self._prolog_epilog = PrologEpilog(self, "prolog-epilog")

        # #### Charm lifecycle events #### #
        event_handler_bindings = {
            # #### Juju lifecycle events #### #
            self.on.install: self._on_install,
            self.on.config_changed: self._on_check_status_and_write_config,
            # ######## Addons lifecycle events ######## #
            self._elasticsearch.on.elasticsearch_available: self._on_check_status_and_write_config,
            self._elasticsearch.on.elasticsearch_unavailable: self._on_check_status_and_write_config,
            self._grafana.on.grafana_available: self._on_grafana_available,
            self._influxdb.on.influxdb_available: self._on_influxdb_available,
            self._influxdb.on.influxdb_unavailable: self._on_check_status_and_write_config,
            # ######## Slurm component lifecycle events ######## #
            self._slurmctld.on.slurmctld_available: self._on_check_status_and_write_config,
            self._slurmctld.on.slurmctld_unavailable: self._on_check_status_and_write_config,
            self._slurmdbd.on.slurmdbd_available: self._on_check_status_and_write_config,
            self._slurmdbd.on.slurmdbd_unavailable: self._on_check_status_and_write_config,
            self._slurmd.on.slurmd_available: self._on_check_status_and_write_config,
            self._slurmd.on.slurmd_unavailable: self._on_check_status_and_write_config,
            self._slurmrestd.on.slurmrestd_available: self._on_slurmrestd_available,
            self._slurmrestd.on.slurmrestd_unavailable: self._on_check_status_and_write_config,
            self._prolog_epilog.on.prolog_epilog_available: self._on_check_status_and_write_config,
            self._prolog_epilog.on.prolog_epilog_unavailable: self._on_check_status_and_write_config,
            # Actions
            self.on.scontrol_reconfigure_action: self._on_scontrol_reconfigure,
            self.on.show_current_config_action: self._on_show_current_config,
            self.on.show_new_config_action: self._on_show_new_config,
            self.on.reconfigure_slurm_action: self._on_reconfigure_slurm,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_scontrol_reconfigure(self, event):
        """Run 'scontrol reconfigure' on slurmctld."""
        self._slurmctld.scontrol_reconfigure()

    def _on_show_current_config(self, event):
        """Show current slurm.conf."""
        slurm_conf = self._slurm_manager.get_slurm_conf()
        event.set_results({"slurm.conf": slurm_conf})

    def _on_show_new_config(self, event):
        """Assemble and show a new slurm.conf, without saving it."""
        slurm_conf = self._assemble_slurm_config()
        event.set_results({"slurm.conf": slurm_conf})

    def _on_reconfigure_slurm(self, event):
        """Force a new slurm.conf to be used in all nodes."""
        self._stored.force_reconfiguration = True
        self._on_check_status_and_write_config(event)
        event.set_results({"reconfigured": True})

    def _on_install(self, event):
        """Install slurm and capture the munge key."""
        self._slurm_manager.install()

        # Store the munge_key and jwt_rsa key in the stored state.
        #
        # NOTE: Use leadership settings instead of stored state when
        # leadership settings support becomes available in the framework.
        if self._is_leader():
            self._stored.jwt_rsa = self._slurm_manager.generate_jwt_rsa()
            self._stored.munge_key = self._slurm_manager.get_munge_key()

        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("slurm installed")

        self._slurm_manager.start_munged()

    def _on_grafana_available(self, event):
        """Create the grafana-source if we are the leader and have influxdb."""
        leader = self._is_leader()
        influxdb_info = self._get_influxdb_info()
        grafana = self._grafana

        if leader and influxdb_info:
            grafana.set_grafana_source_info(influxdb_info)

    def _on_influxdb_available(self, event):
        """Create the grafana-source if we have all the things."""
        grafana = self._grafana
        influxdb_info = self._get_influxdb_info()
        leader = self._is_leader()

        if leader and grafana.is_joined and influxdb_info:
            grafana.set_grafana_source_info(influxdb_info)

        self._on_check_status_and_write_config(event)

    def _on_slurmrestd_available(self, event):
        """Set slurm_config on the relation when slurmrestd available."""
        if not self._check_status():
            event.defer()
            return

        # Generate the slurm_config
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

    def _on_check_status_and_write_config(self, event):
        """Check that we have what we need before we proceed."""
        if not self._check_status():
            event.defer()
            return

        logger.debug("### Configurator - check status write config ()")

        # Generate the slurm_config
        slurm_config = self._assemble_slurm_config()

        if not slurm_config:
            self.unit.status = BlockedStatus(
                "Cannot generate slurm_config - defering event."
            )
            event.defer()
            return

        if self._stored.force_reconfiguration:
            self._stored.force_reconfiguration = False
            slurm_config['force_reconfiguration'] = str(uuid.uuid4())

        self._slurmctld.set_slurm_config_on_app_relation_data(
            slurm_config,
        )
        self._slurmctld.restart_slurmctld()

        self._slurmd.set_slurm_config_on_app_relation_data(
            slurm_config,
        )

        if self._stored.slurmrestd_available:
            self._slurmrestd.set_slurm_config_on_app_relation_data(
                slurm_config,
            )
            self._slurmrestd.restart_slurmrestd()

        self._slurm_manager.render_slurm_configs(slurm_config)

        if not self._stored.slurmd_restarted:
            self._slurm_manager.restart_slurm_component()
            self._stored.slurmd_restarted = True

        self._slurmctld.scontrol_reconfigure()

        # get "not new anymore" nodes
        down_nodes = slurm_config["down_nodes"]
        configured_nodes = self._assemble_configured_nodes(down_nodes)
        logger.debug(f"### issuing 'scontrol update' for: {down_nodes}")
        self._slurmctld.scontrol_update(configured_nodes)
        # update down nodes cache
        self._stored.down_nodes = down_nodes.copy()

    def _assemble_slurm_config(self):
        """Assemble and return the slurm config."""
        slurmctld_info = self._slurmctld.get_slurmctld_info()
        slurmdbd_info = self._slurmdbd.get_slurmdbd_info()
        slurmd_info = self._slurmd.get_slurmd_info()

        if not (slurmd_info and slurmctld_info and slurmdbd_info):
            return {}

        addons_info = self._assemble_addons()
        partitions_info = self._assemble_partitions(slurmd_info)
        down_nodes = self._assemble_down_nodes(slurmd_info)

        logger.debug(addons_info)
        logger.debug(partitions_info)
        logger.debug(slurmctld_info)
        logger.debug(slurmdbd_info)
        logger.debug(f"#### _assemble_slurm_config() Down nodes: {down_nodes}")

        return {
            "partitions": partitions_info,
            "down_nodes": down_nodes,
            **slurmctld_info,
            **slurmdbd_info,
            **addons_info,
            **self.config,
        }

    def _assemble_partitions(self, slurmd_info):
        """Make any needed modifications to partition data."""
        slurmd_info_tmp = copy.deepcopy(slurmd_info)
        default_partition_from_config = self.config.get("default_partition")

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
            if not default_partition_from_config:
                if partition["partition_name"] == "configurator":
                    partition_tmp["partition_default"] = "YES"
            else:
                if default_partition_from_config == partition_name:
                    partition_tmp["partition_default"] = "YES"

            slurmd_info_tmp.remove(partition)
            slurmd_info_tmp.append(partition_tmp)

        return slurmd_info_tmp

    @staticmethod
    def _assemble_down_nodes(slurmd_info):
        """Parse partitions' nodes and assemble a list of DownNodes."""
        down_nodes = []
        for partition in slurmd_info:
            # we don't care about the configurator partition
            # also it does not have the "new_node" key
            if partition["partition_name"] != "configurator":
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

    def _assemble_addons(self):
        """Assemble any addon components."""
        acct_gather = self._get_influxdb_info()
        elasticsearch_ingress = self._elasticsearch.get_elasticsearch_ingress()
        prolog_epilog = self._prolog_epilog.get_prolog_epilog()

        ctxt = dict()

        if prolog_epilog:
            ctxt["prolog_epilog"] = prolog_epilog

        if acct_gather:
            ctxt["acct_gather"] = acct_gather
            acct_gather_custom = self.config.get("acct_gather_custom")
            if acct_gather_custom:
                ctxt["acct_gather"]["custom"] = acct_gather_custom

        if elasticsearch_ingress:
            ctxt["elasticsearch_address"] = elasticsearch_ingress

        return ctxt

    def _check_status(self):
        """Check that the core components we need exist."""
        slurm_component_statuses = {
            "slurmctld": {
                "available": self._stored.slurmctld_available,
                "joined": self._slurmctld.is_joined,
            },
            "slurmd": {
                "available": self._stored.slurmd_available,
                "joined": self._slurmd.is_joined,
            },
            "slurmdbd": {
                "available": self._stored.slurmdbd_available,
                "joined": self._slurmdbd.is_joined,
            },
        }

        relations_needed = []
        waiting_on = []

        msg = str()

        for slurm_component in slurm_component_statuses.keys():
            if not slurm_component_statuses[slurm_component]["joined"]:
                relations_needed.append(slurm_component)
            elif not slurm_component_statuses[slurm_component]["available"]:
                waiting_on.append(slurm_component)

        relations_needed_len = len(relations_needed)
        waiting_on_len = len(waiting_on)

        if relations_needed_len > 0:
            msg += f"Needed relations: {','.join(relations_needed)} "

        if waiting_on_len > 0:
            msg += f"Waiting on: {','.join(waiting_on)}"

        # Using what we have gathered about the status of each slurm component,
        # determine the application status.
        if relations_needed_len > 0:
            self.unit.status = BlockedStatus(msg)
        elif waiting_on_len > 0:
            self.unit.status = WaitingStatus(msg)
        else:
            self.unit.status = ActiveStatus("slurm-configurator available")
            return True
        return False

    def _get_influxdb_info(self):
        """Return influxdb info."""
        return self._influxdb.get_influxdb_info()

    def _is_leader(self):
        return self.model.unit.is_leader()

    def get_munge_key(self):
        """Return the slurmdbd_info from stored state."""
        return self._stored.munge_key

    def get_jwt_rsa(self):
        """Return the jwt rsa key."""
        return self._stored.jwt_rsa

    def is_slurm_installed(self):
        """Return true/false based on whether or not slurm is installed."""
        return self._stored.slurm_installed

    def set_slurmctld_available(self, slurmctld_available):
        """Set slurmctld_available."""
        self._stored.slurmctld_available = slurmctld_available

    def set_slurmdbd_available(self, slurmdbd_available):
        """Set slurmdbd_available."""
        self._stored.slurmdbd_available = slurmdbd_available

    def set_slurmd_available(self, slurmd_available):
        """Set slurmd_available."""
        self._stored.slurmd_available = slurmd_available

    def set_slurmrestd_available(self, slurmrestd_available):
        """Set slurmrestd_available."""
        self._stored.slurmrestd_available = slurmrestd_available


if __name__ == "__main__":
    main(SlurmConfiguratorCharm)
