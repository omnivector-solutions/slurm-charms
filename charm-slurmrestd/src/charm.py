#!/usr/bin/env python3
"""SlurmrestdCharm."""
import logging
from pathlib import Path

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    WaitingStatus,
)
from slurm_ops_manager import SlurmManager
from interface_slurmrestd import SlurmrestdRequires

from charms.fluentbit.v0.fluentbit import FluentbitClient

logger = logging.getLogger()


class SlurmrestdCharm(CharmBase):
    """Operator charm responsible for lifecycle operations for slurmrestd."""

    _stored = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        self._stored.set_default(
            slurm_installed=False,
            slurmrestd_restarted=False,
            cluster_name=str()
        )

        self._slurm_manager = SlurmManager(self, "slurmrestd")
        self._slurmrestd = SlurmrestdRequires(self, 'slurmrestd')
        self._fluentbit = FluentbitClient(self, "fluentbit")

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.upgrade_charm: self._on_upgrade,
            self.on.update_status: self._on_update_status,
            self._slurmrestd.on.config_available: self._on_check_status_and_write_config,
            self._slurmrestd.on.config_unavailable: self._on_config_unavailable,
            self._slurmrestd.on.munge_key_available: self._on_configure_munge_key,
            self._slurmrestd.on.jwt_rsa_available: self._on_configure_jwt_rsa,
            self._slurmrestd.on.restart_slurmrestd: self._on_restart_slurmrestd,
            # fluentbit
            self.on["fluentbit"].relation_created: self._on_fluentbit_relation_created,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        """Perform installation operations for slurmrestd."""
        self.unit.set_workload_version(Path("version").read_text().strip())

        self.unit.status = WaitingStatus("Installing slurmrestd")

        custom_repo = self.config.get("custom-slurm-repo")
        successful_installation = self._slurm_manager.install(custom_repo)

        if successful_installation:
            self.unit.status = ActiveStatus("slurmrestd installed")
            self._stored.slurm_installed = True

            self._slurm_manager.start_munged()
        else:
            self.unit.status = BlockedStatus("Error installing slurmrestd")
            event.defer()

        self._check_status()

    def _on_fluentbit_relation_created(self, event):
        """Set up Fluentbit log forwarding."""
        self._configure_fluentbit()

    def _configure_fluentbit(self):
        logger.debug("## Configuring fluentbit")
        cfg = list()
        cfg.extend(self._slurm_manager.fluentbit_config_nhc)
        cfg.extend(self._slurm_manager.fluentbit_config_slurm)
        self._fluentbit.configure(cfg)

    def _on_upgrade(self, event):
        """Perform upgrade operations."""
        self.unit.set_workload_version(Path("version").read_text().strip())
        self._check_status()

    def _on_update_status(self, event):
        """Handle update status."""
        self._check_status()

    def _on_config_unavailable(self, event):
        """Handle the config unavailable due to relation broken."""
        # when the config becomes unavailable, we have to set this flag to False,
        # so the next time the config becoms avaiable, the daemon restarts
        self._stored.slurmrestd_restarted = False
        self._check_status()

    def _on_restart_slurmrestd(self, event):
        """Resart the slurmrestd component."""
        logger.debug("## _on_restart_slurmrestd")

        if not self._check_status():
            event.defer()
            return

        self._slurm_manager.restart_slurm_component()
        self._stored.slurmrestd_restarted = True

    def _on_configure_munge_key(self, event):
        """Configure the munge key.

        1) Get the munge key from the stored state of the slurmrestd relation
        2) Write the munge key to the munge key path and chmod
        3) Restart munged
        """
        if not self._stored.slurm_installed:
            event.defer()
            return

        logger.debug("## configuring new munge key")
        munge_key = self._slurmrestd.get_stored_munge_key()
        self._slurm_manager.configure_munge_key(munge_key)
        self._slurm_manager.restart_munged()

    def _on_configure_jwt_rsa(self, event):
        if not self._stored.slurm_installed:
            event.defer()
            return

        logger.debug("## configuring new jwt rsa")
        jwt_rsa = self._slurmrestd.get_stored_jwt_rsa()
        self._slurm_manager.configure_jwt_rsa(jwt_rsa)

    def _check_status(self) -> bool:
        if self._slurm_manager.needs_reboot:
            self.unit.status = BlockedStatus("Machine needs reboot")
            return False

        if not self._stored.slurm_installed:
            self.unit.status = BlockedStatus("Error installing slurmrestd")
            return False

        # Check and see if we have what we need for operation.
        if not self._slurmrestd.is_joined:
            self.unit.status = BlockedStatus("Need relations: slurmctld")
            return False

        slurmctld_available = (self._slurmrestd.get_stored_munge_key()
                               and self._slurmrestd.get_stored_jwt_rsa()
                               and self._slurmrestd.get_stored_slurm_config())
        if not slurmctld_available:
            self.unit.status = WaitingStatus("Waiting on: slurmctld")
            return True

        self.unit.status = ActiveStatus("slurmrestd available")

        return True

    def _on_check_status_and_write_config(self, event):
        if not self._check_status():
            event.defer()
            return

        slurm_config = self._slurmrestd.get_stored_slurm_config()
        if slurm_config:
            self._slurm_manager.render_slurm_configs(slurm_config)
            self.cluster_name = slurm_config.get("cluster_name")
        else:
            logger.error(f"## weird slurmconfig: {slurm_config}")

        # Only restart slurmrestd the first time the node is brought up.
        if not self._stored.slurmrestd_restarted:
            self._on_restart_slurmrestd(event)

        if self._fluentbit._relation is not None:
            self._configure_fluentbit()

    @property
    def cluster_name(self) -> str:
        """Return the cluster-name."""
        return self._stored.cluster_name

    @cluster_name.setter
    def cluster_name(self, name: str):
        """Set the cluster-name."""
        self._stored.cluster_name = name


if __name__ == "__main__":
    main(SlurmrestdCharm)
