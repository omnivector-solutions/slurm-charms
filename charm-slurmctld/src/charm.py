#!/usr/bin/python3
"""SlurmctldCharm."""
import logging

from interface_slurmctld import Slurmctld
from interface_slurmctld_peer import SlurmctldPeer
from nrpe_external_master import Nrpe
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmManager


logger = logging.getLogger()


class SlurmctldCharm(CharmBase):
    """Slurmctld lifecycle events."""

    _stored = StoredState()

    def __init__(self, *args):
        """Init _stored attributes and interfaces, observe events."""
        super().__init__(*args)

        self._stored.set_default(
            munge_key=str(),
            slurmctld_controller_type=str(),
        )

        self._nrpe = Nrpe(self, "nrpe-external-master")

        self._slurm_manager = SlurmManager(self, "slurmctld")

        self._slurmctld = Slurmctld(self, "slurmctld")
        self._slurmctld_peer = SlurmctldPeer(self, "slurmctld-peer")

        event_handler_bindings = {
            self.on.install: self._on_install,

            self._slurmctld.on.slurm_config_available:
            self._on_check_status_and_write_config,

            self._slurmctld_peer.on.slurmctld_peer_available:
            self._on_slurmctld_peer_available,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self._slurm_manager.install()
        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("Slurm Installed")

    def _on_upgrade(self, event):
        self._slurm_manager.upgrade()

    def _on_slurmctld_peer_available(self, event):
        if self.framework.model.unit.is_leader():
            if self._slurmctld.is_joined:
                slurmctld_info = self._slurmctld_peer.get_slurmctld_info()
                if slurmctld_info:
                    self._slurmctld.set_slurmctld_info_on_app_relation_data(
                        slurmctld_info
                    )
                    return
            event.defer()
            return

    def _on_check_status_and_write_config(self, event):
        if not self._check_status():
            event.defer()
            return

        slurm_config = self._slurmctld.get_slurm_config_from_relation()
        if not slurm_config:
            event.defer()
            return

        munge_key = self._stored.munge_key
        if not munge_key:
            event.defer()
            return

        self._slurm_manager.render_config_and_restart(
            {
                **slurm_config,
                'munge_key': munge_key
            }
        )
        self.unit.status = ActiveStatus("Slurmctld Available")

    def _check_status(self):
        munge_key = self._stored.munge_key
        slurm_installed = self._stored.slurm_installed
        slurm_config = self._slurmctld.get_slurm_config_from_relation()

        if not (munge_key and slurm_installed and slurm_config):
            if not munge_key:
                self.unit.status = BlockedStatus(
                    "NEED RELATION TO SLURM CONFIGURATOR"
                )
            elif not slurm_config:
                self.unit.status = BlockedStatus(
                    "WAITING ON SLURM CONFIG"
                )
            else:
                self.unit.status = BlockedStatus("SLURM NOT INSTALLED")
            return False
        else:
            return True

    def set_munge_key(self, munge_key):
        """Set the munge_key in _stored state."""
        self._stored.munge_key = munge_key

    def get_slurm_component(self):
        """Return the slurm component."""
        return self._slurm_manager.slurm_component

    def get_hostname(self):
        """Return the hostname."""
        return self._slurm_manager.hostname

    def get_port(self):
        """Return the port."""
        return self._slurm_manager.port


if __name__ == "__main__":
    main(SlurmctldCharm)
