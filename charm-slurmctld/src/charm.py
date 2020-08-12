#!/usr/bin/python3
"""SlurmctldCharm."""
import logging

from elasticsearch_requires import ElasticsearchRequires
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_login_provides import SlurmLoginProvides
from slurm_ops_manager import SlurmOpsManager
from slurmd_requires import SlurmdRequires
from slurmdbd_requires import SlurmdbdRequiresRelation
from slurmrestd_provides import SlurmrestdProvides


logger = logging.getLogger()


class SlurmctldCharm(CharmBase):
    """Operator charm responsible for lifecycle operations for slurmctld."""

    _stored = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        self._stored.set_default(
            munge_key=str(),
            elasticsearch_ingress=None,
            slurmdbd_info=dict(),
            slurm_installed=False,
            slurmdbd_available=False,
            slurmd_available=False,
            slurmrestd_available=False,
            login_available=False,

        )
        self.elasticsearch = ElasticsearchRequires(self, "elasticsearch")
        self.slurm_ops_manager = SlurmOpsManager(self, "slurmctld")
        self.slurmdbd = SlurmdbdRequiresRelation(self, "slurmdbd")
        self.slurmd = SlurmdRequires(self, "slurmd")
        self.slurm_login_provides = SlurmLoginProvides(self, "login")
        self.slurmrestd_provides = SlurmrestdProvides(self, "slurmrestd")

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

            self.slurmrestd_provides.on.slurmrestd_available:
            self._on_provide_slurmrestd,

            self.elasticsearch.on.elasticsearch_available:
            self._on_check_status_and_write_config,


        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self.slurm_ops_manager.install()
        self._stored.munge_key = self.slurm_ops_manager.get_munge_key()
        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("Slurm Installed")

    def _on_check_status_and_write_config(self, event):
        if not self._check_status(event):
            event.defer()
            return
        slurm_config = self._assemble_slurm_config()

        self.slurmd.set_slurm_config_on_app_relation_data(
            'slurmd',
            slurm_config,
        )
        if self._stored.slurmrestd_available:
            self.slurmd.set_slurm_config_on_app_relation_data(
                'slurmrestd',
                slurm_config,
            )
        if self._stored.login_available:
            self.slurmd.set_slurm_config_on_app_relation_data(
                'login',
                slurm_config,
            )
        self.slurm_ops_manager.render_config_and_restart(slurm_config)
        self.unit.status = ActiveStatus("Slurmctld Available")

    def _on_provide_slurmrestd(self, event):
        if not self._check_status(event):
            event.defer()
            return

        slurm_config = self._assemble_slurm_config()
        self.slurmd.set_slurm_config_on_app_relation_data(
            'slurmrestd',
            slurm_config,
        )

    def _assemble_slurm_config(self):
        slurm_config = self.slurmd.get_slurm_config()
        elasticsearch_endpoint = self._stored.elasticsearch_ingress

        if elasticsearch_endpoint:
            slurm_config = {
                **slurm_config,
                **{'elasticsearch_address': elasticsearch_endpoint},
            }
        return slurm_config

    def _check_status(self, event):
        slurmdbd_acquired = self._stored.slurmdbd_available
        slurmd_acquired = self._stored.slurmd_available
        slurm_installed = self._stored.slurm_installed

        if not (slurmdbd_acquired and slurmd_acquired and slurm_installed):
            if not slurmd_acquired:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMD")
            elif not slurmdbd_acquired:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMDBD")
            else:
                self.unit.status = BlockedStatus("SLURM NOT INSTALLED")
            return False
        else:
            return True

    def is_slurmd_available(self):
        """Set stored state slurmd_available."""
        return self._stored.slurmd_available

    def is_slurmdbd_available(self):
        """Set stored state slurmdbd_available."""
        return self._stored.slurmdbd_available

    def is_slurm_installed(self):
        """Return true/false based on whether or not slurm is installed."""
        return self._stored.slurm_installed

    def is_slurm_login_available(self):
        """Return slurm_login_acquired from local stored state."""
        return self._stored.slurm_login_available

    def is_slurmrestd_available(self):
        """Return slurmrestd_acquired from local stored state."""
        return self._stored.slurmrestd_available

    def get_munge_key(self):
        """Get the slurmdbd_info from stored state."""
        return self._stored.munge_key

    def get_slurm_config(self):
        """Return slurm_config from local stored state."""
        return self._stored.slurm_config

    def get_slurmdbd_info(self):
        """Get the slurmdbd_info from stored state."""
        return self._stored.slurmdbd_info

    def set_slurmdbd_info(self, slurmdbd_info):
        """Set the slurmdbd_info in local stored state."""
        self._stored.slurmdbd_info = slurmdbd_info

    def set_slurm_config(self, slurm_config):
        """Set the slurm_config in local stored state."""
        self._stored.slurm_config = slurm_config

    def set_slurmdbd_available(self, slurmdbd_available):
        """Set stored state slurmdbd_available."""
        self._stored.slurmdbd_available = slurmdbd_available

    def set_slurmd_available(self, slurmd_available):
        """Set stored state slurmd_available."""
        self._stored.slurmd_available = slurmd_available

    def set_slurmrestd_available(self, slurmrestd_available):
        """Set stored state slurmrestd_available."""
        self._stored.slurmrestd_available = slurmrestd_available

    def set_slurm_login_available(self, slurm_login_available):
        """Set stored state slurm_login_available."""
        self._stored.login_available = slurm_login_available


if __name__ == "__main__":
    main(SlurmctldCharm)
