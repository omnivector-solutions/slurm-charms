#!/usr/bin/env python3
"""SlurmdCharm."""
import base64
import logging
from pathlib import Path
from time import sleep

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
            slurm_installed=False,
            slurmctld_available=False,
        )

        self._slurm_manager = SlurmManager(self, "slurmd")

        self._slurmd = Slurmd(self, "slurmd")
        self._slurmd_peer = SlurmdPeer(self, "slurmd-peer")

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.config_changed: self._on_config_changed,
            self._slurmd.on.munge_key_available: self._on_write_munge_key,
            self._slurmd_peer.on.slurmd_peer_available: self._on_set_partition_info_on_app_relation_data,
            self._slurmd_peer.on.slurmd_peer_departed: self._on_set_partition_info_on_app_relation_data,
            self._slurmd.on.slurmctld_available: self._on_slurmctld_available,
            # actions
            self.on.version_action: self._on_version_action,
            self.on.node_configured_action: self._on_node_configured_action,
            self.on.get_node_inventory_action: self._on_get_node_inventory_action,
            self.on.show_nhc_config_action: self._on_show_nhc_config,
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
        """Perform installation operations for slurmd."""
        self.unit.set_workload_version(Path("VERSION").read_text().strip())

        self.unit.status = WaitingStatus("Installing slurmd")

        successful_installation = self._slurm_manager.install()
        logger.debug(f"### slurmd installed: {successful_installation}")

        if successful_installation:
            self._stored.slurm_installed = True

            if self.model.unit.is_leader():
                self._get_set_partition_name()
                logger.debug(f"PARTITION_NAME: {self._stored.partition_name}")
        else:
            self.unit.status = BlockedStatus("Error installing slurm")
            event.defer()

        self._check_status()

    def _check_status(self) -> bool:
        """Check if we heve all needed components.

        - slurm installed,
        - slurmctld available and working,
        - munge key
        """
        if not self._stored.slurm_installed:
            self.unit.status = BlockedStatus("Error installing slurm")
            return False

        if not (self._stored.slurmctld_available and self._slurmd.is_joined):
            self.unit.status = WaitingStatus("Waiting on slurmctld relation")
            return False

        if not self._stored.munge_key_available:
            self.unit.status = WaitingStatus("Waiting munge key")
            return False

        self.unit.status = ActiveStatus("Slurmd available")
        return True

    def _check_slurmd(self, max_attemps=3):
        """Ensure slurmd is up and running."""
        logger.debug("## Checking if slurmd is active")

        for i in range(max_attemps):
            if self._slurm_manager.slurm_is_active():
                logger.debug("## Slurmd running")
                break
            else:
                logger.warning("## Slurmd not running, trying to start it")
                self.unit.status = WaitingStatus("Starting slurmd")
                sleep(1 + i)

                self._slurm_manager.restart_slurm_component()

        if self._slurm_manager.slurm_is_active():
            self._check_status()

    def set_slurmctld_available(self, flag: bool):
        """Change stored value for slurmctld availability."""
        self._stored.slurmctld_available = flag

    def _on_slurmctld_available(self, event):
        if not self._check_status():
            event.defer()
            return

        logger.debug('#### Slurmctld available - setting overrides for configless')
        # get slurmctld host:port from relation and override systemd services
        host = self._slurmd.slurmctld_hostname
        port = self._slurmd.slurmctld_port

        self._slurm_manager.create_configless_systemd_override(host, port)
        self._slurm_manager.daemon_reload()

        self._on_set_partition_info_on_app_relation_data(event)
        self._slurm_manager.slurm_systemctl('restart')
        self._check_slurmd()

    def _on_config_changed(self, event):
        if self.model.unit.is_leader():
            self._get_set_partition_name()
            self._on_set_partition_info_on_app_relation_data(event)

        nhc_conf = self.model.config.get('nhc-conf')
        if nhc_conf:
            if nhc_conf != self._stored.nhc_conf:
                self._stored.nhc_conf = nhc_conf
                self._slurm_manager.render_nhc_config(nhc_conf)

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

    def _on_version_action(self, event):
        """Return version of installed components.

        - Slurm
        - munge
        - NHC
        - infiniband
        """
        version = {}
        version['slurm'] = self._slurm_manager.slurm_version()
        version['munge'] = self._slurm_manager.munge_version()
        version['nhc'] = self._slurm_manager.nhc_version()
        version['infiniband'] = self._slurm_manager.infiniband_version()

        event.set_results(version)

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

    def _on_show_nhc_config(self, event):
        """Show current nhc.conf."""
        nhc_conf = self._slurm_manager.get_nhc_config()
        event.set_results({"nhc.conf": nhc_conf})

    def _on_set_partition_info_on_app_relation_data(self, event):
        """Set the slurm partition info on the application relation data."""
        # Only the leader can set data on the relation.
        if self.framework.model.unit.is_leader():
            # If the relation with slurmctld exists then set our
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
