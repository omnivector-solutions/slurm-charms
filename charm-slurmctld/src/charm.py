#!/usr/bin/python3
"""SlurmctldCharm."""
import logging

from elasticsearch_requires import ElasticsearchRequires
from nhc_requires import NhcRequires
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmManager
from slurmd_requires import SlurmdRequires
from slurmdbd_requires import SlurmdbdRequiresRelation
from slurmrestd_provides import SlurmrestdProvides


logger = logging.getLogger()

VERSION = '1.0.1'


class SlurmctldCharm(CharmBase):
    """Operator charm responsible for lifecycle operations for slurmctld."""

    _stored = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        self.unit.set_workload_version(VERSION)

        self._stored.set_default(
            munge_key=str(),
            nhc_info=dict(),
            elasticsearch_ingress=None,
            slurmdbd_info=dict(),
            slurm_installed=False,
            slurmd_available=False,
            slurmrestd_available=False,

        )
        self._elasticsearch = ElasticsearchRequires(self, "elasticsearch")
        self._nhc_requires = NhcRequires(self, "nhc")

        self._slurm_manager = SlurmManager(self, "slurmctld")

        self._slurmdbd = SlurmdbdRequiresRelation(self, "slurmdbd")
        self._slurmd = SlurmdRequires(self, "slurmd")
        self._slurmrestd_provides = SlurmrestdProvides(self, "slurmrestd")

        event_handler_bindings = {
            self.on.install: self._on_install,

            self.on.start:
            self._on_check_status_and_write_config,

            self.on.config_changed:
            self._on_check_status_and_write_config,

            self.on.upgrade_charm: self._on_upgrade,

            self._slurmdbd.on.slurmdbd_available:
            self._on_check_status_and_write_config,

            self._slurmdbd.on.slurmdbd_unavailable:
            self._on_check_status_and_write_config,

            self._slurmd.on.slurmd_available:
            self._on_check_status_and_write_config,

            self._slurmd.on.slurmd_departed:
            self._on_check_status_and_write_config,

            self._slurmd.on.slurmd_unavailable:
            self._on_check_status_and_write_config,

            self._slurmrestd_provides.on.slurmrestd_available:
            self._on_provide_slurmrestd,

            self._elasticsearch.on.elasticsearch_available:
            self._on_check_status_and_write_config,

            self._nhc_requires.on.nhc_bin_available:
            self._on_check_status_and_write_config,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self._slurm_manager.install()
        self._stored.munge_key = self._slurm_manager.get_munge_key()
        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("Slurm Installed")

    def _on_upgrade(self, event):
        logger.debug('_on_upgrade(): entering')
        slurm_config = self._assemble_slurm_config()
        self._slurm_manager.upgrade(slurm_config)

    def _on_check_status_and_write_config(self, event):
        logger.debug('_on_check_status_and_write_config(): entering')
        if not self._check_status():
            event.defer()
            return

        slurm_config = self._assemble_slurm_config()
        if not slurm_config:
            event.defer()
            return

        self._slurm_manager.render_config_and_restart(slurm_config)

        self._slurmd.set_slurm_config_on_app_relation_data(
            'slurmd',
            slurm_config,
        )
        if self._stored.slurmrestd_available:
            self._slurmd.set_slurm_config_on_app_relation_data(
                'slurmrestd',
                slurm_config,
            )
        self.unit.status = ActiveStatus("Slurmctld Available")

    def _on_provide_slurmrestd(self, event):
        if not self._check_status():
            event.defer()
            return

        slurm_config = self._assemble_slurm_config()
        if not slurm_config:
            event.defer()
            return

        self._slurmd.set_slurm_config_on_app_relation_data(
            'slurmrestd',
            slurm_config,
        )

    def _assemble_slurm_config(self):
        slurm_config = self._slurmd.get_slurm_config()
        if not slurm_config:
            return None

        elasticsearch_endpoint = self._stored.elasticsearch_ingress
        nhc_info = self._stored.nhc_info

        ctxt = {
            'nhc': {},
            'elasticsearch_address': "",
        }
        if nhc_info:
            ctxt['nhc']['nhc_bin'] = nhc_info['nhc_bin']
            ctxt['nhc']['health_check_interval'] = \
                nhc_info['health_check_interval']
            ctxt['nhc']['health_check_node_state'] = \
                nhc_info['health_check_node_state']

        if elasticsearch_endpoint:
            ctxt['elasticsearch_address'] = elasticsearch_endpoint

        return {**slurm_config, **ctxt}

    def _check_status(self):
        slurmdbd_info = self._stored.slurmdbd_info
        slurmd_acquired = self._stored.slurmd_available
        slurm_installed = self._stored.slurm_installed

        if not (slurmdbd_info and slurmd_acquired and slurm_installed):
            if not slurmd_acquired:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMD")
            elif not slurmdbd_info:
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

    def set_nhc_info(self, nhc_info):
        """Set the nhc_info in local stored state."""
        self._stored.nhc_info = nhc_info


if __name__ == "__main__":
    main(SlurmctldCharm)
