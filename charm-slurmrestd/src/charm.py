#!/usr/bin/python3
"""SlurmLoginCharm."""
import logging

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmOpsManager
from slurmrestd_requires import SlurmrestdRequires


logger = logging.getLogger()


class SlurmLoginCharm(CharmBase):
    """Operator charm responsible for lifecycle operations for slurmctld."""

    _stored = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)
        self._stored.set_default(
            slurm_config=dict(),
            slurm_installed=False,
            slurmctld_available=False,
        )
        self.slurm_ops_manager = SlurmOpsManager(self, "slurmrestd")
        self._slurmrestd = SlurmrestdRequires(self, 'slurmrestd')

        event_handler_bindings = {
            self.on.install:
            self._on_install,

            self.on.start:
            self._on_check_status_and_write_config,

            self._slurmrestd.on.slurmctld_available:
            self._on_check_status_and_write_config,

            self._slurmrestd.on.slurmctld_unavailable:
            self._on_check_status_and_write_config,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self.slurm_ops_manager.install()
        self.unit.status = ActiveStatus("slurm installed")
        self._stored.slurm_installed = True

    def _on_check_status_and_write_config(self, event):
        slurm_installed = self._stored.slurm_installed
        slurmctld_acquired = self._stored.slurmctld_available

        if not (slurm_installed and slurmctld_acquired):
            if not slurmctld_acquired:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMCTLD")
            else:
                self.unit.status = BlockedStatus("SLURM NOT INSTALLED")
            event.defer()
            return
        else:
            config = dict(self._stored.slurm_config)
            self.slurm_ops_manager.render_config_and_restart(config)
            self.unit.status = ActiveStatus("Slurmrestd Available")

    def is_slurmctld_available(self):
        """Return self._stored.slurmctld_available."""
        return self._stored.slurmctld_available

    def set_slurm_config(self, slurm_config):
        """Set self._stored.slurm_config."""
        self._stored.slurm_config = slurm_config

    def set_slurmctld_available(self, slurmctld_available):
        """Set self._stored.slurmctld_available."""
        self._stored.slurmctld_available = slurmctld_available


if __name__ == "__main__":
    main(SlurmLoginCharm)
