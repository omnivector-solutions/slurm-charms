#!/usr/bin/python3
"""SlurmctldCharm."""
import logging


from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmOpsManager
from slurmd_requires import SlurmdRequires
from slurmdbd_requires import SlurmdbdRequiresRelation


logger = logging.getLogger()


class SlurmctldCharm(CharmBase):
    """Operator charm responsible for lifecycle operations for slurmctld."""

    _stored = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        self._stored.set_default(
            slurmdbd_info=dict(),
            slurm_installed=False,
            slurmdbd_available=False,
            slurmd_available=False,
            login_available=False,
            restd_available=False,
            slurm_config=None,
        )
        self.slurm_ops_manager = SlurmOpsManager(self, "slurmctld")
        self.slurmdbd = SlurmdbdRequiresRelation(self, "slurmdbd")
        self.slurmd = SlurmdRequires(self, "slurmd")
        # self.login = LoginProvides(self, "login")
        # self.slurm_restd = RestdProvides(self, "slurmrestd")

        event_handler_bindings = {
            self.on.install:
            self._on_install,

            self.on.start:
            self._on_check_status_and_write_config,

            self.on.config_changed:
            self._on_check_status_and_write_config,

            self.slurmdbd.on.slurmdbd_available:
            self._on_check_status_and_write_config,

            self.slurmdbd.on.slurmdbd_unavailable:
            self._on_check_status_and_write_config,

            self.slurmd.on.slurmd_available:
            self._on_check_status_and_write_config,

            self.slurmd.on.slurmd_unavailable:
            self._on_check_status_and_write_config,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self.slurm_ops_manager.install()
        self.unit.status = ActiveStatus("Slurm Installed")
        self._stored.slurm_installed = True

    def _on_check_status_and_write_config(self, event):
        slurmdbd_acquired = self._stored.slurmdbd_available
        slurmd_acquired = self._stored.slurmd_available
        slurm_installed = self._stored.slurm_installed
        if (slurmdbd_acquired and slurmd_acquired and slurm_installed):
            self.slurm_ops_manager.render_config_and_restart(
                self._stored.slurm_config
            )
            self.unit.status = ActiveStatus("Slurmctld Available")
        else:
            if not slurmdbd_acquired:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMDBD")
            else:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMD")
            event.defer()
            return

    def set_slurmdbd_info(self, slurmdbd_info):
        """Set the slurmdbd_info in local stored state."""
        self._stored.slurmdbd_info = slurmdbd_info

    def get_slurmdbd_info(self):
        """Get the slurmdbd_info from stored state."""
        return self._stored.slurmdbd_info

    def set_slurmdbd_available(self, slurmdbd_available):
        """Set stored state slurmdbd_available."""
        self._stored.slurmdbd_available = slurmdbd_available

    def set_slurmd_available(self, slurmd_available):
        """Set stored state slurmd_available."""
        self._stored.slurmd_available = slurmd_available

    def is_slurmdbd_available(self):
        """Set stored state slurmdbd_available."""
        return self._stored.slurmdbd_available

    def is_slurm_installed(self):
        """Return true/false based on whether or not slurm is installed."""
        return self._stored.slurm_installed


if __name__ == "__main__":
    main(SlurmctldCharm)
