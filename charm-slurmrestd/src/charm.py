#!/usr/bin/env python3
"""SlurmrestdCharm."""
import logging

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
        )
        self._slurm_manager = SlurmManager(self, "slurmrestd")
        self._slurmrestd = SlurmrestdRequires(self, 'slurmrestd')

        event_handler_bindings = {
            self.on.install: self._on_install,
            self._slurmrestd.on.config_available: self._on_check_status_and_write_config,
            self._slurmrestd.on.munge_key_available: self._on_configure_munge_key,
            self._slurmrestd.on.restart_slurmrestd: self._on_restart_slurmrestd,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self._slurm_manager.install()
        self.unit.status = ActiveStatus("slurm installed")
        self._stored.slurm_installed = True

        self._slurm_manager.start_munged()

    def _on_restart_slurmrestd(self, event):
        """Resart the slurmrestd component."""
        self._slurm_manager.restart_slurm_component()

    def _on_configure_munge_key(self, event):
        """Configure the munge key.

        1) Get the munge key from the stored state of the slurmrestd relation
        2) Write the munge key to the munge key path and chmod
        3) Restart munged
        4) Set munge_key_available in charm stored state
        """
        if not self._stored.slurm_installed:
            event.defer()
            return
        munge_key = self._slurmrestd.get_stored_munge_key()
        self._slurm_manager.configure_munge_key(munge_key)
        self._slurm_manager.restart_munged()
        self._stored.munge_key_available = True

    def _check_status(self):
        slurm_config = self._slurmrestd.get_stored_slurm_config()
        munge_key_available = self._stored.munge_key_available

        slurm_configurator_joined = self._slurmrestd.is_joined

        # Check and see if we have what we need for operation.
        if not slurm_configurator_joined:
            self.unit.status = BlockedStatus(
                "Needed relations: slurm-configurator"
            )
            return None
        elif not (munge_key_available and slurm_config):
            self.unit.status = WaitingStatus(
                "Waiting on: configuration"
            )
            return None

        return dict(slurm_config)

    def _on_check_status_and_write_config(self, event):
        slurm_config = self._check_status()
        if not slurm_config:
            event.defer()
            return

        self._slurm_manager.render_slurm_configs(slurm_config)

        # Only restart slurmrestd the first time the node is brought up.
        if not self._stored.slurmrestd_restarted:
            self._slurm_manager.restart_slurm_component()
            self._stored.slurmrestd_restarted = True

        self.unit.status = ActiveStatus("slurmrestd available")


if __name__ == "__main__":
    main(SlurmrestdCharm)
