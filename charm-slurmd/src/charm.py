#!/usr/bin/env python3
"""SlurmdCharm."""
import base64
import logging

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
            partition_name=str(),
            nhc_conf=str(),
            health_check_interval=int(),
            health_check_state=str(),
            slurm_installed=False,
        )

        self._slurm_manager = SlurmManager(self, "slurmd")

        self._slurmd = Slurmd(self, "slurmd")
        self._slurmd_peer = SlurmdPeer(self, "slurmd-peer")

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.config_changed: self._on_config_changed,
            self._slurmd.on.munge_key_available: self._on_write_munge_key,
            self._slurmd_peer.on.slurmd_peer_departed: self._on_set_partition_info_on_app_relation_data,
            self._slurmd.on.slurmctld_available: self._on_slurmctld_available,
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

    def _on_slurmctld_available(self, event):
        if not self._stored.slurm_installed:
            event.defer()
            return

        logger.debug('#### Slurmctld available - setting overrides for configless')
        # get slurmctld host:port from relation and override systemd services
        host = self._slurmd.slurmctld_hostname
        port = self._slurmd.slurmctld_port

        self._slurm_manager.create_configless_systemd_override(host, port)
        self._slurm_manager.daemon_reload()
        self._slurm_manager.slurm_systemctl('restart')

        self._on_set_partition_info_on_app_relation_data(event)

    def _on_config_changed(self, event):
        reconfigure_slurm = False

        if self.model.unit.is_leader():
            self._get_set_partition_name()
            self._on_set_partition_info_on_app_relation_data(
                event
            )

        nhc_conf = self.model.config.get('nhc-conf')
        if nhc_conf:
            if nhc_conf != self._stored.nhc_conf:
                self._stored.nhc_conf = nhc_conf
                self._slurm_manager.render_nhc_config(nhc_conf)

        # TODO: move these to slurmctld
        #health_check_interval = self.model.config.get('health-check-interval')
        #if health_check_interval:
        #    if health_check_interval != self._stored.health_check_interval:
        #        self._stored.health_check_interval = health_check_interval
        #        reconfigure_slurm = True

        #health_check_state = self.model.config.get('health-check-state')
        #if health_check_state:
        #    if health_check_state != self._stored.health_check_state:
        #        self._stored.health_check_state = health_check_state
        #        reconfigure_slurm = True

    def _on_write_munge_key(self, event):
        if not self._stored.slurm_installed:
            event.defer()
            return

        logger.debug('#### slurmd charm - writting munge key')
        self._slurm_manager.configure_munge_key(
            self._slurmd.get_stored_munge_key()
        )
        self._slurm_manager.restart_munged()
        self._stored.munge_key_available = True

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
        repo = base64.b64decode(repo).decode()
        self._slurm_manager.infiniband.repository = repo

    def install_infiniband(self, event):
        """Install infiniband."""
        logger.debug("#### Installing Infiniband")
        self._slurm_manager.infiniband.install()
        event.set_results({'installation': 'Successfull. Please reboot node.'})
        self.unit.status = BlockedStatus("Need reboot for Infiniband")

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

    def _on_show_nhc_config(self, event):
        """Show current nhc.conf."""
        nhc_conf = self._slurm_manager.get_nhc_config()
        event.set_results({"nhc.conf": nhc_conf})

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
                else:
                    event.defer()
            # unneeded possible breakage
            # https://www.pivotaltracker.com/story/show/177270742
            else:
                event.defer()

    def _assemble_partition(self):
        """Assemble the partition info."""
        partition_name = self._stored.partition_name
        partition_config = self.config.get("partition-config")
        partition_state = self.config.get("partition-state")

        slurmd_inventory = self._slurmd_peer.get_slurmd_inventory()
        if not slurmd_inventory:
            return None

        return {
            "inventory": slurmd_inventory,
            "partition_name": partition_name,
            "partition_state": partition_state,
            "partition_config": partition_config,
        }

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

    @property
    def hostname(self):
        """Return the hostname."""
        return self._slurm_manager.hostname


if __name__ == "__main__":
    main(SlurmdCharm)
