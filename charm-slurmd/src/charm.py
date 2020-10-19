#!/usr/bin/python3
"""SlurmdCharm."""
import copy
import logging

from interface_slurmd import Slurmd
from interface_slurmd_peer import SlurmdPeer
from nrpe_external_master import Nrpe
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmManager
from utils import random_string


logger = logging.getLogger()


class SlurmdCharm(CharmBase):
    """Slurmd lifecycle events."""

    _stored = StoredState()

    def __init__(self, *args):
        """Init _stored attributes and interfaces, observe events."""
        super().__init__(*args)

        self._stored.set_default(
            munge_key=str(),
            user_node_state=str(),
            partition_name=str(),
        )

        self._nrpe = Nrpe(self, "nrpe-external-master")

        self._slurm_manager = SlurmManager(self, "slurmd")

        self._slurmd = Slurmd(self, "slurmd")
        self._slurmd_peer = SlurmdPeer(self, "slurmd-peer")

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.upgrade_charm: self._on_upgrade,

            self.on.start:
            self._on_check_status_and_write_config,

            self.on.config_changed:
            self._on_config_changed,

            self._slurmd_peer.on.slurmd_peer_available:
            self._on_send_slurmd_info,

            self._slurmd.on.slurm_config_available:
            self._on_check_status_and_write_config,

            self.on.set_node_state_action:
            self._on_set_node_state_action,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self._slurm_manager.install()

        if self.model.unit.is_leader():
            self._get_set_partition_name()
            logger.debug("LOGGING PARTITION_NAME")
            logger.debug(self._stored.partition_name)

        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("Slurm Installed")

    def _on_upgrade(self, event):
        slurmd_info = self._assemble_slurmd_info()
        self._slurm_manager.upgrade(slurmd_info)

    def _on_config_changed(self, event):
        if self.model.unit.is_leader():
            self._get_set_partition_name()
            if self._check_status():
                self._on_send_slurmd_info(event)

    def _on_set_node_state_action(self, event):
        """Set the node state."""
        self._stored.user_node_state = event.params["node-state"]
        self._on_send_slurm_info(event)

    def _on_send_slurmd_info(self, event):
        if self.framework.model.unit.is_leader():
            if self._slurmd.is_joined:
                partition = self._assemble_partition()
                if partition:
                    self._slurmd.set_slurmd_info_on_app_relation_data(
                        partition
                    )
                    return
            event.defer()
            return

    def _on_check_status_and_write_config(self, event):
        if not self._check_status():
            event.defer()
            return

        slurm_config = self._slurmd.get_slurm_config()
        if not slurm_config:
            event.defer()
            return

        munge_key = self._stored.munge_key
        if not munge_key:
            event.defer()
            return

        self._slurm_manager.render_config_and_restart(
            {**slurm_config, 'munge_key': munge_key}
        )
        self.unit.status = ActiveStatus("Slurmd Available")

    def _check_status(self):
        munge_key = self._stored.munge_key
        slurm_installed = self._stored.slurm_installed
        slurm_config_available = self._slurmd.get_slurm_config()

        if not (munge_key and slurm_installed and slurm_config_available):
            if not munge_key:
                self.unit.status = BlockedStatus(
                    "NEED RELATION TO SLURM CONFIGURATOR"
                )
            elif not slurm_config_available:
                self.unit.status = BlockedStatus(
                    "WAITING ON SLURM CONFIG"
                )
            else:
                self.unit.status = BlockedStatus("SLURM NOT INSTALLED")
            return False
        else:
            return True

    def _assemble_partition(self):
        """Assemble the partition info."""
        partition_name = self._stored.partition_name
        partition_config = self.model.config.get('partition-config')
        partition_state = self.model.config.get('partition-state')

        slurmd_info = self._assemble_slurmd_info()

        return {
            'inventory': slurmd_info,
            'partition_name': partition_name,
            'partition_state': partition_state,
            'partition_config': partition_config,
        }

    def _assemble_slurmd_info(self):
        """Apply mutations to nodes in the partition, return slurmd nodes."""
        slurmd_info = self._slurmd_peer.get_slurmd_info()
        if not slurmd_info:
            return None

        # If the user has set custom state for nodes
        # ensure we update the state for the targeted nodes.
        user_node_state = self._stored.user_node_state
        if user_node_state:
            node_states = {
                item.split("=")[0]: item.split("=")[1]
                for item in user_node_state.split(",")
            }

            # Copy the slurmd_info returned from the the slurmd-peer relation
            # to a temporary variable to which we will make modifications.
            slurmd_info_tmp = copy.deepcopy(slurmd_info)

            # Iterate over the slurmd nodes in the partition and check
            # for nodes that need their state modified.
            for partition in slurmd_info:
                partition_tmp = copy.deepcopy(partition)
                for slurmd_node in partition['inventory']:
                    if slurmd_node['hostname'] in node_states.keys():
                        slurmd_node_tmp = copy.deepcopy(slurmd_node)
                        slurmd_node_tmp['state'] = \
                            node_states[slurmd_node['hostname']]
                        partition_tmp['inventory'].remove(slurmd_node)
                        partition_tmp['inventory'].append(slurmd_node_tmp)
                slurmd_info_tmp.remove(partition)
                slurmd_info_tmp.append(partition_tmp)
        else:
            slurmd_info_tmp = slurmd_info

        return slurmd_info_tmp

    def _get_set_partition_name(self):
        """Set the partition name."""
        # Determine if a partition-name config exists, if so
        # ensure the self._stored.partition_name is consistent with the
        # supplied config.
        # If no partition name has been specified then generate one.
        partition_name = self.model.config.get('partition-name')
        if partition_name:
            if partition_name != self._stored.partition_name:
                self._stored.partition_name = partition_name
        elif not self._stored.partition_name:
            self._stored.partition_name = f"juju-compute-{random_string()}"
        return

    def set_munge_key(self, munge_key):
        """Set the munge key."""
        self._stored.munge_key = munge_key

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
