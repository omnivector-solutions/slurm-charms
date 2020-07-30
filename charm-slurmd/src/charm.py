#! /usr/bin/env python3
"""libraries needed for charm."""
import json
import logging

from ops.charm import CharmBase
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from ops.framework import StoredState
from slurm_ops_manager import SlurmOpsManager

from slurmd_provides import SlurmdProvides

logger = logging.getLogger()


class SlurmdCharm(CharmBase):
    """Operator charm responsible for coordinating lifecycle operations for slurmd."""
    _stored = StoredState()
    def __init__(self, *args):
        """Initialize charm, configure states, and events to observe."""
        super().__init__(*args)
        self.config = self.model.config
        self.slurm_ops_manager = SlurmOpsManager(self, 'slurmd')
        self.slurmd = SlurmdProvides(self, "slurmd")
        
        self._stored.set_default(
            slurm_installed = False,
            config_available = False,
            slurm_config = dict(),
        )
        event_handler_bindings = {
            self.on.install: self._on_install,
            self.slurmd.on.config_available: self._on_slurmd_available,
            self.slurmd.on.config_unavailable: self._on_slurmd_available
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        """Install the slurm scheduler as snap or tar file."""
        self.slurm_ops_manager.install()
        self.unit.status = ActiveStatus("Slurm Installed")
        self._stored.slurm_installed = True

    def _on_slurmd_available(self, event):
        """Retrieve info of other slurmd nodes from controller to write
        to slurm.conf
        """
        if self._stored.slurm_installed and self._stored.config_available:
            # need to cast to normal python dict instead of operator object
            slurm_config = dict(self._stored.slurm_config)
            self.slurm_ops_manager.render_config_and_restart(slurm_config)
            self.unit.status = ActiveStatus("Slurmd Available")
        else:
            self.unit.status = BlockedStatus("Blocked need relation to slurmctld.")
            event.defer()
            return

if __name__ == "__main__":
    main(SlurmdCharm)
