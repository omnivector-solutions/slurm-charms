#!/usr/bin/env python3
"""SlurmdCharm."""
import copy
import logging

from nrpe_external_master import Nrpe
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from slurm_ops_manager import SlurmManager

from interface_slurmd import Slurmd
from interface_slurmd_peer import SlurmdPeer
from utils import random_string

logger = logging.getLogger()


class SlurmdCharm(CharmBase):
    """Slurmd lifecycle events."""

    _stored = StoredState()

    def __init__(self, *args):
        """Init _stored attributes and interfaces, observe events."""
        super().__init__(*args)

        self._stored.set_default(
            munge_key_available=False,
            slurmd_restarted=False,
            user_node_state=str(),
            partition_name=str(),
            nhc_conf=str(),
        )

        self._nrpe = Nrpe(self, "nrpe-external-master")

        self._slurm_manager = SlurmManager(self, "slurmd")

        self._slurmd = Slurmd(self, "slurmd")
        self._slurmd_peer = SlurmdPeer(self, "slurmd-peer")

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.start: self._on_check_status_and_write_config,
            self.on.config_changed: self._on_config_changed,
            self._slurmd_peer.on.slurmd_peer_available:
            self._on_set_partition_info_on_app_relation_data,
            self._slurmd_peer.on.slurmd_peer_departed:
            self._on_set_partition_info_on_app_relation_data,
            self._slurmd.on.slurm_config_available:
            self._on_check_status_and_write_config,
            self._slurmd.on.slurm_config_unavailable:
            self._on_check_status_and_write_config,
            self._slurmd.on.restart_slurmd: self._on_restart_slurmd,
            self._slurmd.on.munge_key_available: self._on_write_munge_key,
            # actions
            self.on.set_node_state_action: self._on_set_node_state_action,
            self.on.node_configured_action: self._on_node_configured_action,
            self.on.get_node_inventory_action:
            self._on_get_node_inventory_action,
            self.on.show_current_config_action: self._on_show_current_config,
            # infiniband actions
            self.on.get_infiniband_repo_action: self.get_infiniband_repo,
            self.on.set_infiniband_repo_action: self.set_infiniband_repo,
            self.on.install_infiniband_action: self.install_infiniband,
            self.on.uninstall_infiniband_action: self.uninstall_infiniband,
            self.on.start_infiniband_action: self.start_infiniband,
            self.on.enable_infiniband_action: self.enable_infiniband,
            self.on.stop_infiniband_action: self.stop_infiniband,
            self.on.is_active_infiniband_action: self.is_active_infiniband,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self._slurm_manager.install()

        if self.model.unit.is_leader():
            self._get_set_partition_name()
            logger.debug(f"PARTITION_NAME: {self._stored.partition_name}")
        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("Slurm installed")

        self._slurm_manager.start_munged()

    def _on_config_changed(self, event):
        if self.model.unit.is_leader():
            self._get_set_partition_name()
            if self._check_status():
                self._on_set_partition_info_on_app_relation_data(
                    event
                )

        nhc_conf = self.model.config.get('nhc-conf')
        if nhc_conf:
            if nhc_conf != self._stored.nhc_conf:
                self._stored.nhc_conf = nhc_conf
                self._slurm_manager.render_nhc_config(nhc_conf)

    def _on_write_munge_key(self, event):
        if not self._stored.slurm_installed:
            event.defer()
            return
        munge_key = self._slurmd.get_stored_munge_key()
        self._slurm_manager.configure_munge_key(munge_key)
        self._slurm_manager.restart_munged()
        self._stored.munge_key_available = True

    def _on_check_status_and_write_config(self, event):
        slurm_config = self._check_status()
        if not slurm_config:
            event.defer()
            return

        # if slurm_config['configless']:
        #    slurmctld_hostname = slurm_config['active_controller_hostname']
        #    self._slurm_manager.configure_slurmctld_hostname(
        #        slurmctld_hostname
        #    )
        #    self._slurm_manager.restart_slurm_component()
        # else:

        # Ensure we aren't dealing with a StoredDict before trying
        # to render the slurm.conf.
        slurm_config = dict(slurm_config)
        # NOTE: slurm_config_nhc_values allows to change the interval and note
        # state. Could be turned into config.yaml options later.
        slurm_config.update(self._slurm_manager.slurm_config_nhc_values())
        self._slurm_manager.render_slurm_configs(slurm_config)

        # Only restart slurmd the first time the node is brought up.
        if not self._stored.slurmd_restarted:
            self._slurm_manager.restart_slurm_component()
            self._stored.slurmd_restarted = True

        self.unit.status = ActiveStatus("slurmd available")

    def _on_restart_slurmd(self, event):
        self._slurm_manager.restart_slurm_component()

    def _check_status(self):
        munge_key_available = self._stored.munge_key_available
        slurm_installed = self._stored.slurm_installed
        slurm_config = self._slurmd.get_stored_slurm_config()

        slurmd_joined = self._slurmd.is_joined

        if not slurmd_joined:
            self.unit.status = BlockedStatus(
                "Needed relations: slurm-configurator"
            )
            return None

        elif not (munge_key_available and slurm_config and slurm_installed):
            self.unit.status = WaitingStatus(
                "Waiting on: configuration"
            )
            return None

        return dict(slurm_config)

    def _on_set_node_state_action(self, event):
        """Set the node state."""
        self._stored.user_node_state = event.params["node-state"]
        self._on_set_partition_info_on_app_relation_data(event)

    def _on_node_configured_action(self, event):
        """Remove node from DownNodes."""
        # trigger reconfig
        self._slurmd_peer.configure_new_node()
        logger.debug('### This node is not new anymore')

    def _on_get_node_inventory_action(self, event):
        """Return node inventory."""
        inventory = self._slurmd_peer.get_node_inventory()
        event.set_results({'inventory': inventory})

    def get_infiniband_repo(self, event):
        """Return the currently used infiniband repository."""
        repo = self._slurm_manager.infiniband.repository
        event.set_results({'infiniband-repo': repo})

    def set_infiniband_repo(self, event):
        """Set the infiniband repository."""
        repo = event.params["repo"]
        logger.debug(f"#### setting custom infiniband repo: {repo}")
        self._slurm_manager.infiniband.repository = repo

    def install_infiniband(self, event):
        """Install infiniband."""
        logger.debug("#### Installing Infiniband")
        self._slurm_manager.infiniband.install()
        event.set_results({'installation': 'Successfull. Please reboot node.'})

    def uninstall_infiniband(self, event):
        """Install infiniband."""
        logger.debug("#### Uninstalling Infiniband")
        self._slurm_manager.infiniband.uninstall()

    def start_infiniband(self, event):
        """Start Infiniband systemd service."""
        logger.debug("#### Starting Infiniband service")
        self._slurm_manager.infiniband.start()

    def enable_infiniband(self, event):
        """Enable Infiniband systemd service."""
        logger.debug("#### Enabling Infiniband service")
        self._slurm_manager.infiniband.enable()

    def stop_infiniband(self, event):
        """Stop Infiniband systemd service."""
        logger.debug("#### Stoping Infiniband service")
        self._slurm_manager.infiniband.stop()

    def is_active_infiniband(self, event):
        """Check if Infiniband systemd service is arctive."""
        status = self._slurm_manager.infiniband.is_active()
        logger.debug(f"#### Infiniband service is-active: {status}")
        event.set_results({'infiniband-is-active': status})

    def _on_show_current_config(self, event):
        """Show current slurm.conf."""
        slurm_conf = self._slurm_manager.get_slurm_conf()
        event.set_results({"slurm.conf": slurm_conf})

    def _on_set_partition_info_on_app_relation_data(self, event):
        """Set the slurm partition info on the application relation data."""
        # Only the leader can set data on the relation.
        if self.framework.model.unit.is_leader():
            # If the relation with slurm-configurator exists then set our
            # partition info on the application relation data.
            # This handler shouldn't fire if the relation isn't made,
            # but add this extra check here just incase.
            if self._slurmd.is_joined:
                partition = self._assemble_partition()
                if partition:
                    self._slurmd.set_partition_info_on_app_relation_data(
                        partition
                    )
                    return
            # unneeded possible breakage
            # https://www.pivotaltracker.com/story/show/177270742
            # event.defer()
            return

    def _assemble_partition(self):
        """Assemble the partition info."""
        partition_name = self._stored.partition_name
        partition_config = self.config.get("partition-config")
        partition_state = self.config.get("partition-state")

        slurmd_inventory = self._assemble_slurmd_inventory()

        return {
            "inventory": slurmd_inventory,
            "partition_name": partition_name,
            "partition_state": partition_state,
            "partition_config": partition_config,
        }

    def _assemble_slurmd_inventory(self):
        """Apply mutations to nodes in the partition, return slurmd nodes."""
        slurmd_inventory = self._slurmd_peer.get_slurmd_inventory()
        if not slurmd_inventory:
            return None

        # If the user has set custom state for nodes
        # ensure we update the state for the targeted nodes.
        user_node_state = self._stored.user_node_state
        if user_node_state:
            node_states = {
                item.split("=")[0]: item.split("=")[1]
                for item in user_node_state.split(",")
            }

            # Copy the slurmd_inventory returned from the the slurmd-peer
            # relation to a temporary variable that we will use to
            # iterate over while we conditionally make modifications to the
            # original inventory.
            slurmd_inventory_tmp = copy.deepcopy(slurmd_inventory)

            # Iterate over the slurmd nodes in the partition and check
            # for nodes that need their state modified.
            for partition in slurmd_inventory_tmp:
                partition_tmp = copy.deepcopy(partition)
                for slurmd_node in partition["inventory"]:
                    if slurmd_node["hostname"] in node_states.keys():
                        slurmd_node_tmp = copy.deepcopy(slurmd_node)
                        slurmd_node_tmp["state"] = \
                            node_states[slurmd_node["hostname"]]
                        partition_tmp["inventory"].remove(slurmd_node)
                        partition_tmp["inventory"].append(slurmd_node_tmp)
                slurmd_inventory.remove(partition)
                slurmd_inventory.append(partition_tmp)

        return slurmd_inventory

    def _get_set_partition_name(self):
        """Set the partition name."""
        # Determine if a partition-name config exists, if so
        # ensure the self._stored.partition_name is consistent with the
        # supplied config.
        # If no partition name has been specified then generate one.
        partition_name = self.config.get("partition-name")
        if partition_name:
            if partition_name != self._stored.partition_name:
                self._stored.partition_name = partition_name
        elif not self._stored.partition_name:
            self._stored.partition_name = f"juju-compute-{random_string()}"
        return

    def get_partition_name(self):
        """Return the partition_name."""
        return self._stored.partition_name

    def get_slurm_component(self):
        """Return the slurm component."""
        return self._slurm_manager.slurm_component

    def get_hostname(self):
        """Return the hostname."""
        return self._slurm_manager.hostname

    def get_port(self):
        """Return the port."""
        return self._slurm_manager.port


if __name__ == "__main__":
    main(SlurmdCharm)
