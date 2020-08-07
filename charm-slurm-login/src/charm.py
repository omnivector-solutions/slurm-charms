#! /usr/bin/env python3
"""libraries needed for charm."""
import logging

from ops.charm import CharmBase
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    WaitingStatus,
)
from ops.framework import StoredState

from slurm_ops_manager import SlurmOpsManager

from login_requires import LoginRequires

logger = logging.getLogger()


class SlurmLoginCharm(CharmBase):
    """Operator charm responsible for lifecycle operations for slurmctld."""
    _stored = StoredState()
    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)
        self._stored.set_default(
            slurm_config = None,
            slurm_installed = False,
            )
        self.slurm_ops_manager = SlurmOpsManager(self, "none")
        self._login = LoginRequires(self, 'login')


        event_handler_bindings = {
            self.on.install:
            self._on_install,

            self.on.start:
            self._on_start,

            self._login.on.config_available:
            self._on_config_available,

        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self.slurm_ops_manager.install()
        self.unit.status = ActiveStatus("slurm installed")
        self._stored.slurm_installed = True

    def _on_start(self, event):
        if not self._stored.slurm_config:
            self.unit.status = BlockedStatus("need relation to slurmctld")

    def _on_config_available(self, event):
        if not self._stored.slurm_installed:
            event.defer()
            return
        else:
            config = dict(self._stored.slurm_config)
            self.slurm_ops_manager.render_config_and_restart(config)
            self.unit.status = ActiveStatus("Login Charm Available")

if __name__ == "__main__":
    main(SlurmLoginCharm)
