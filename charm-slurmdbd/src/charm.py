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

        self._stored.set_default(db_info=None)
        self._stored.set_default(db_info_acquired=False)
        self._stored.set_default(munge_key_available=False)
        self._stored.set_default(slurm_installed=False)

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
        logger.debug("database available")

        self._stored.db_info_acquired = True
        _write_config_and_restart_slurmdbd(self, event)

    def _on_munge_key_available(self, event):
        logger.debug("ctld available")
        self._stored.munge_key_available = True
        _write_config_and_restart_slurmdbd(self, event)

    def _on_slurmctld_unavailable(self, event):
        self.unit.status = BlockedStatus("Need relation to slurmctld.")


def _write_config_and_restart_slurmdbd(charm, event):
    """Check for prerequisites before writing config/restart of slurmdbd."""
    if not (charm._stored.db_info_acquired and
            charm._stored.slurm_installed and
            charm._stored.munge_key_available):
        if not charm._stored.db_info_acquired:
            charm.unit.status = BlockedStatus("Need relation to MySQL.")
        elif not charm._stored.munge_key_available:
            charm.unit.status = BlockedStatus("Need relation to slurmctld.")
        event.defer()
        return

    slurmdbd_host_port_addr = {
        'slurmdbd_hostname': socket.gethostname().split(".")[0],
        'slurmdbd_port': "6819",
    }
    slurmdbd_config = {
        'munge_key': charm.slurmdbd.munge_key,
        **slurmdbd_host_port_addr,
        **charm.model.config,
        **charm._stored.db_info,
    }
    charm.slurm_ops_manager.render_config_and_restart(slurmdbd_config)
    charm.slurmdbd.set_slurmdbd_available_on_unit_relation_data("true")
    charm.unit.status = ActiveStatus("Slurmdbd Available")


if __name__ == "__main__":
    main(SlurmdbdCharm)
