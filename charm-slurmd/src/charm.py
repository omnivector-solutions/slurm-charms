#!/usr/bin/env python3
"""SlurmdCharm."""
import logging

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmOpsManager
from slurmd_provides import SlurmdProvides

logger = logging.getLogger()


class SlurmdCharm(CharmBase):
    """Operator charm responsible for coordinating lifecycle operations for slurmd."""

    _stored = StoredState()

    def __init__(self, *args):
        """Initialize charm state, and observe charm lifecycle events."""
        super().__init__(*args)

        self.config = self.model.config
        self.slurm_ops_manager = SlurmOpsManager(self, 'slurmd')
        self.slurmd = SlurmdProvides(self, "slurmd")

        self._stored.set_default(
            slurm_installed=False,
            slurm_config_available=False,
            slurm_config=dict(),
        )

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.config_changed: self._on_render_config_and_restart,
            self.slurmd.on.slurmctld_available:
            self._on_render_config_and_restart,
            self.slurmd.on.slurmctld_unavailable:
            self._on_render_config_and_restart,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        """Install the slurm scheduler as snap or tar file."""
        self.slurm_ops_manager.install()
        self.unit.status = ActiveStatus("Slurm Installed")
        self._stored.slurm_installed = True

    def _on_render_config_and_restart(self, event):
        """Retrieve slurm_config from controller and write slurm.conf."""
        if self._stored.slurm_installed and self._stored.slurm_config_available:
            # cast StoredState -> python dict
            slurm_config = dict(self._stored.slurm_config)
            self.slurm_ops_manager.render_config_and_restart(slurm_config)
            self.unit.status = ActiveStatus("Slurmd Available")
        else:
            self.unit.status = BlockedStatus("Blocked need relation to slurmctld.")
            event.defer()
            return

    def set_slurm_config_available(self, config_available):
        """Set slurm_config_available in local stored state."""
        self._stored.slurm_config_available = config_available

    def set_slurm_config(self, slurm_config):
        """Set the slurm_config in local stored state."""
        self._stored.slurm_config = slurm_config

    def is_slurm_installed(self):
        """Return true/false based on whether or not slurm is installed."""
        return self._stored.slurm_installed


if __name__ == "__main__":
    main(SlurmdCharm)
