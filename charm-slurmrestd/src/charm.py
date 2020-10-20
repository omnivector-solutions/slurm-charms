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
from slurm_ops_manager import SlurmManager
from slurmrestd_requires import SlurmrestdRequires


logger = logging.getLogger()


class SlurmLoginCharm(CharmBase):
    """Operator charm responsible for lifecycle operations for slurmctld."""

    _stored = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)
        self._stored.set_default(
            slurm_installed=False,
            config_available=False,
        )
        self.slurm_manager = SlurmManager(self, "slurmrestd")
        self._slurmrestd = SlurmrestdRequires(self, 'slurmrestd')

        event_handler_bindings = {
            self.on.install:
            self._on_install,

            self.on.upgrade_charm: self._on_upgrade,

            self._slurmrestd.on.config_available:
            self._on_check_status_and_write_config,

            self._slurmrestd.on.config_unavailable:
            self._on_check_status_and_write_config,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self.slurm_manager.install()
        self.unit.status = ActiveStatus("slurm installed")
        self._stored.slurm_installed = True

    def _on_upgrade(self, event):
        """Upgrade charm event handler."""
        self.slurm_manager.upgrade()

    def _on_check_status_and_write_config(self, event):
        slurm_installed = self._stored.slurm_installed
        slurm_config = self._stored.config_available
        logger.debug("##### inside check status and write config ######")
        if not (slurm_installed and slurm_config):
            if not slurm_config:
                self.unit.status = BlockedStatus(
                    "NEED RELATION TO SLURM-CONFIGURATOR"
                )
            else:
                self.unit.status = BlockedStatus("SLURM NOT INSTALLED")
            event.defer()
            return
        else:
            logger.debug("##### STATUS CONFIRMED ######")
            config = dict(self._slurmrestd.get_slurm_config())
            logger.debug(config)
            self.slurm_manager.render_config_and_restart(config)
            self.unit.status = ActiveStatus("Slurmrestd Available")

    def set_config_available(self, boolean):
        """Set self._stored.slurmctld_available."""
        self._stored.config_available = boolean


if __name__ == "__main__":
    main(SlurmLoginCharm)
