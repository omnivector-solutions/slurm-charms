#!/usr/bin/python3
"""Slurmdbd Operator Charm."""
import logging
import socket

<<<<<<< HEAD
from interface_mysql import MySQLClient
=======

from mysql_requires import MySQLClient
>>>>>>> 5b6be961010cb4d984b7064ccacc4ec910b8e9c9
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmManager
from slurmdbd_provides import SlurmdbdProvidesRelation


logger = logging.getLogger()


class SlurmdbdCharm(CharmBase):
    """Slurmdbd Charm Class."""

    _stored = StoredState()

    def __init__(self, *args):
        """Set the defaults for slurmdbd."""
        super().__init__(*args)

        self._stored.set_default(db_info=dict())
        self._stored.set_default(munge_key=str())
        self._stored.set_default(slurm_installed=False)

<<<<<<< HEAD
        self.slurm_ops_manager = SlurmManager(self, "slurmdbd")
        self.slurmdbd = SlurmdbdProvidesRelation(self, "slurmdbd")
=======
        self._slurm_manager = SlurmManager(self, "slurmdbd")
        self._slurmdbd = SlurmdbdProvidesRelation(self, "slurmdbd")
>>>>>>> 5b6be961010cb4d984b7064ccacc4ec910b8e9c9

        self._db = MySQLClient(self, "db")

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.config_changed: self._write_config_and_restart_slurmdbd,
            self._db.on.database_available:
            self._write_config_and_restart_slurmdbd,
            self._slurmdbd.on.munge_key_available:
            self._write_config_and_restart_slurmdbd,
            self._slurmdbd.on.slurmctld_unavailable:
            self._on_slurmctld_unavailable,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self._slurm_manager.install()
        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("Slurm Installed")

    def _on_upgrade(self, event):
        """Handle upgrade charm event."""
        self._slurm_manager.upgrade()

    def _on_slurmctld_unavailable(self, event):
        self.unit.status = BlockedStatus("Need relation to slurmctld.")

    def _check_status(self) -> bool:
        """Check that we have the things we need."""
        db_info = self._stored.db_info
        munge_key = self._stored.munge_key
        slurm_installed = self._stored.slurm_installed

        if not (db_info and slurm_installed and munge_key):
            if not self._stored.db_info:
                self.unit.status = BlockedStatus("Need relation to MySQL.")
            elif not self._stored.munge_key:
                self.unit.status = BlockedStatus("Need relation to slurmctld.")
            return False
        return True

    def _write_config_and_restart_slurmdbd(self, event):
        """Check for prereqs before writing config/restart of slurmdbd."""
        if not self._check_status():
            event.defer()
            return

        slurmdbd_host_port_addr = {
            'slurmdbd_hostname': socket.gethostname().split(".")[0],
            'slurmdbd_port': "6819",
        }
        slurmdbd_config = {
            'munge_key': self._stored.munge_key,
            **slurmdbd_host_port_addr,
            **self.model.config,
            **self._stored.db_info,
        }
        self._slurm_manager.render_config_and_restart(slurmdbd_config)
        self._slurmdbd.set_slurmdbd_available_on_unit_relation_data()
        self.unit.status = ActiveStatus("Slurmdbd Available")

    def set_munge_key(self, munge_key):
        """Set the munge key in the stored state."""
        self._stored.munge_key = munge_key

    def set_db_info(self, db_info):
        """Set the db_info in the stored state."""
        self._stored.db_info = db_info


if __name__ == "__main__":
    main(SlurmdbdCharm)
