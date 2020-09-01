#!/usr/bin/python3
"""Slurmdbd Operator Charm."""
import logging
import socket


from interface_mysql import MySQLClient
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmOpsManager
from slurmdbd_provides import SlurmdbdProvidesRelation


logger = logging.getLogger()


class SlurmdbdCharm(CharmBase):
    """Slurmdbd Charm Class."""

    _stored = StoredState()

    def __init__(self, *args):
        """Set the defaults for slurmdbd."""
        super().__init__(*args)

        self._stored.set_default(
            db_info=dict(),
            munge_key=str(),
            slurm_installed=False
        )

        self.slurm_ops_manager = SlurmOpsManager(self, "slurmdbd")
        self.slurmdbd = SlurmdbdProvidesRelation(self, "slurmdbd")

        self.db = MySQLClient(self, "db")

        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.config_changed: self._on_config_changed,
            self.db.on.database_available: self._on_database_available,
            self.slurmdbd.on.munge_key_available: self._on_munge_key_available,
            self.slurmdbd.on.slurmctld_unavailable:
            self._on_slurmctld_unavailable,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self.slurm_ops_manager.install()
        self.unit.status = ActiveStatus("Slurm Installed")
        self._stored.slurm_installed = True

    def _on_config_changed(self, event):
        _write_config_and_restart_slurmdbd(self, event)

    def _on_database_available(self, event):
        """Render the database details into the slurmdbd.yaml."""
        self._stored.db_info = {
            'db_username': event.db_info.user,
            'db_password': event.db_info.password,
            'db_hostname': event.db_info.host,
            'db_port': event.db_info.port,
            'db_name': event.db_info.database,
        }

        _write_config_and_restart_slurmdbd(self, event)

    def _on_munge_key_available(self, event):
        self.slurm_ops_manager.write_munge_key_and_restart(
            self._stored.munge_key
        )

    def _on_slurmctld_unavailable(self, event):
        self.unit.status = BlockedStatus("Need relation to slurmctld.")

    def set_munge_key(self, munge_key):
        """Set the munge key in the stored state."""
        self._stored.munge_key = munge_key


def _write_config_and_restart_slurmdbd(charm, event):
    """Check for prerequisites before writing config/restart of slurmdbd."""
    db_info = charm._stored.db_info
    slurm_installed = charm._stored.slurm_installed
    munge_key = charm._stored.munge_key

    if not db_info and slurm_installed and munge_key:
        if not db_info:
            charm.unit.status = BlockedStatus("Need relation to MySQL.")
        elif not munge_key:
            charm.unit.status = BlockedStatus("Need relation to slurmctld.")
        event.defer()
        return

    slurmdbd_host_port_addr = {
        'slurmdbd_hostname': socket.gethostname().split(".")[0],
        'slurmdbd_port': "6819",
    }
    slurmdbd_config = {
        **slurmdbd_host_port_addr,
        **charm.model.config,
        **db_info
    }
    charm.slurm_ops_manager.render_config_and_restart(slurmdbd_config)
    charm.slurmdbd.set_slurmdbd_available_on_unit_relation_data("true")
    charm.unit.status = ActiveStatus("Slurmdbd Available")


if __name__ == "__main__":
    main(SlurmdbdCharm)
