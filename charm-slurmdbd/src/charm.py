#!/usr/bin/python3
"""Slurmdbd Operator Charm."""
import logging

from interface_mysql import MySQLClient
from interface_slurmdbd import Slurmdbd
from interface_slurmdbd_peer import SlurmdbdPeer
from nrpe_external_master import Nrpe
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus
from slurm_ops_manager import SlurmManager

logger = logging.getLogger()


class SlurmdbdCharm(CharmBase):
    """Slurmdbd Charm."""

    _stored = StoredState()

    def __init__(self, *args):
        """Set the default class attributes."""
        super().__init__(*args)

        self._stored.set_default(
            db_info=dict(),
            slurmdbd_config=dict(),
            slurm_configurator_available=False,
            slurm_installed=False,
        )

        self._db = MySQLClient(self, "db")
        self._nrpe = Nrpe(self, "nrpe-external-master")
        self._slurm_manager = SlurmManager(self, "slurmdbd")
        self._slurmdbd = Slurmdbd(self, "slurmdbd")
        self._slurmdbd_peer = SlurmdbdPeer(self, "slurmdbd-peer")

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.config_changed: self._write_config_and_restart_slurmdbd,
            self._db.on.database_available:
            self._write_config_and_restart_slurmdbd,
            self._slurmdbd_peer.on.slurmdbd_peer_available:
            self._write_config_and_restart_slurmdbd,
            self._slurmdbd.on.slurmdbd_available:
            self._write_config_and_restart_slurmdbd,
            self._slurmdbd.on.slurm_configurator_available:
            self._on_slurm_configurator_available,
            self._slurmdbd.on.slurm_configurator_unavailable:
            self._on_slurm_configurator_unavailable,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self._slurm_manager.install()
        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("slurm successfully installed")

    def _on_slurm_configurator_available(self, event):
        if not self._stored.slurm_installed:
            event.defer()
            return

        # Retrieve and configure the munge_key.
        munge_key = self._slurmdbd.get_munge_key()
        self._slurm_manager.configure_munge_key(munge_key)

        # Retrieve and configure the jwt_rsa key.
        jwt_rsa = self._slurmdbd.get_jwt_rsa()
        self._slurm_manager.configure_jwt_rsa(jwt_rsa)

        # Restart munged and set slurm_configurator_available = True.
        self._slurm_manager.restart_munged()
        self._stored.slurm_configurator_available = True

    def _on_slurm_configurator_unavailable(self, event):
        """Reset state and charm status when slurm-configurator broken."""
        self._stored.slurm_configurator_available = False
        self._check_status()

    def _write_config_and_restart_slurmdbd(self, event):
        """Check for prereqs before writing config/restart of slurmdbd."""
        # Ensure all pre-conditions are met with _check_status(), if not
        # defer the event.
        if not self._check_status():
            event.defer()
            return

        db_info = self._stored.db_info
        slurmdbd_info = self._slurmdbd_peer.get_slurmdbd_info()
        slurmdbd_stored_config = dict(self._stored.slurmdbd_config)

        slurmdbd_config = {
            **self.config,
            **slurmdbd_info,
            **db_info,
        }

        if slurmdbd_config != slurmdbd_stored_config:
            self._stored.slurmdbd_config = slurmdbd_config
            self._slurm_manager.render_slurm_configs(slurmdbd_config)
            self._slurm_manager.restart_slurm_component()

            # Only the leader can set relation data on the application.
            # Enforce that no one other then the leader trys to set
            # application relation data.
            if self.model.unit.is_leader():
                self._slurmdbd.set_slurmdbd_info_on_app_relation_data(
                    slurmdbd_config,
                )
        self.unit.status = ActiveStatus("slurmdbd available")

    def _check_status(self) -> bool:
        """Check that we have the things we need."""
        db_info = self._stored.db_info
        slurm_configurator_available = \
            self._stored.slurm_configurator_available
        slurm_installed = self._stored.slurm_installed
        slurmdbd_info = self._slurmdbd_peer.get_slurmdbd_info()

        deps = [
            slurmdbd_info,
            db_info,
            slurm_installed,
            slurm_configurator_available,
        ]

        if not all(deps):
            if not db_info:
                self.unit.status = BlockedStatus(
                    "Need relation to MySQL."
                )
            elif not slurm_configurator_available:
                self.unit.status = BlockedStatus(
                    "Need relation to slurm-configurator."
                )
            return False
        return True

    def get_port(self):
        """Return the port from slurm-ops-manager."""
        return self._slurm_manager.port

    def get_hostname(self):
        """Return the hostname from slurm-ops-manager."""
        return self._slurm_manager.hostname

    def set_db_info(self, db_info):
        """Set the db_info in the stored state."""
        self._stored.db_info = db_info


if __name__ == "__main__":
    main(SlurmdbdCharm)
