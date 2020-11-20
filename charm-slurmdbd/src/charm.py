#!/usr/bin/python3
"""Slurmdbd Operator Charm."""
import logging
import uuid

from interface_mysql import MySQLClient
from interface_slurmdbd import Slurmdbd
from interface_slurmdbd_peer import SlurmdbdPeer
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


class SlurmdbdCharm(CharmBase):
    """Slurmdbd Charm."""

    _stored = StoredState()

    def __init__(self, *args):
        """Set the default class attributes."""
        super().__init__(*args)

        self._stored.set_default(munge_key=str())
        self._stored.set_default(db_info=dict())
        self._stored.set_default(slurm_installed=False)

        self._nrpe = Nrpe(self, "nrpe-external-master")

        self._slurm_manager = SlurmManager(self, "slurmdbd")

        self._slurmdbd = Slurmdbd(self, "slurmdbd")
        self._slurmdbd_peer = SlurmdbdPeer(self, "slurmdbd-peer")

        self._db = MySQLClient(self, "db")

        event_handler_bindings = {
            self.on.install: self._on_install,

            self.on.config_changed: self._write_config_and_restart_slurmdbd,

            self._db.on.database_available:
            self._write_config_and_restart_slurmdbd,

            self._slurmdbd_peer.on.slurmdbd_peer_available:
            self._write_config_and_restart_slurmdbd,

            self._slurmdbd.on.slurmdbd_available:
            self._write_config_and_restart_slurmdbd,

            self._slurmdbd.on.slurmdbd_unavailable:
            self._on_slurmdbd_unavailable,
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

    def _on_leader_elected(self, event):
        self._slurmdbd_peer._on_relation_changed(event)

    def _on_slurmdbd_unavailable(self, event):
        self._check_status()

    def _check_status(self) -> bool:
        """Check that we have the things we need."""
        db_info = self._stored.db_info
        munge_key = self._stored.munge_key
        slurm_installed = self._stored.slurm_installed
        slurmdbd_info = self._slurmdbd_peer.get_slurmdbd_info()

        deps = [
            slurmdbd_info,
            db_info,
            slurm_installed,
            munge_key,
        ]

        if not all(deps):
            if not db_info:
                self.unit.status = BlockedStatus(
                    "Need relation to MySQL."
                )
            elif not munge_key:
                self.unit.status = BlockedStatus(
                    "Need relation to slurm-configurator."
                )
            return False
        return True

    def _write_config_and_restart_slurmdbd(self, event):
        """Check for prereqs before writing config/restart of slurmdbd."""
        # Ensure all pre-conditions are met with _check_statu(), if not
        # defer the event.
        if not self._check_status():
            event.defer()
            return

        db_info = self._stored.db_info
        slurmdbd_info = self._slurmdbd_peer.get_slurmdbd_info()

        slurmdbd_config = {
            'munge_key': self._stored.munge_key,
            **self.model.config,
            **slurmdbd_info,
            **db_info,
        }

        self._slurm_manager.render_config_and_restart(slurmdbd_config)
        logger.debug("rendering config and restarting")
        # Only the leader can set relation data on the application.
        # Enforce that no one other then the leader trys to set
        # application relation data.
        if self.model.unit.is_leader():
            self._slurmdbd.set_slurmdbd_info_on_app_relation_data(
                {
                    # Juju, and subsequently the operator framework do not
                    # emit relation-changed events if data hasn't actually
                    # changed on the other side of the relation. Even if we set
                    # the data multiple times, it doesn't mean anything unless
                    # the data being set is different then what already exists
                    # in the relation data.
                    #
                    # We use 'slurmdbd_info_id' to ensure the slurmdbd_info
                    # is unique each time it is set on the application relation
                    # data. This is needed so that that related applications
                    # (namely slurm-configurator) will observe a
                    # relation-changed event.
                    #
                    # This event (_write_config_and_restart_slurmdbd) may be
                    # invoked multiple times once _check_status() returns True
                    # (aka pre-conditions are met that account for the deffered
                    # invocations.)
                    # This means that the same slurmdbd_info data may be set on
                    # application data multiple times and slurmdbd may be
                    # reconfigured and restarted while slurmctld and the rest
                    # of the stack are trying to come up and create the clustr.
                    #
                    # We need slurm-configurator to emit the relation-changed
                    # event for the slurmdbd relation every time data is set,
                    # not just when data has changed.
                    # slurm-configurator need to re-emit its chain
                    # of observed events to ensure all services end up getting
                    # reconfigured *and* restarted *after* slurmdbd, for each
                    # time that slurmdbd gets reconfigured and restarted.
                    #
                    # For this reason, 'slurmdbd_info_id' only
                    # matters in the context of making sure the application
                    # relation data actually changes so that relation-changed
                    # event is observed on the other side.
                    'slurmdbd_info_id': str(uuid.uuid4()),
                    **slurmdbd_info
                }
            )
        self.unit.status = ActiveStatus("Slurmdbd Available")

    def get_port(self):
        """Return the port from slurm-ops-manager."""
        return self._slurm_manager.port

    def get_hostname(self):
        """Return the hostname from slurm-ops-manager."""
        return self._slurm_manager.hostname

    def get_slurm_component(self):
        """Return the slurm component."""
        return self._slurm_manager.slurm_component

    def set_munge_key(self, munge_key):
        """Set the munge key in the stored state."""
        self._stored.munge_key = munge_key

    def set_db_info(self, db_info):
        """Set the db_info in the stored state."""
        self._stored.db_info = db_info


if __name__ == "__main__":
    main(SlurmdbdCharm)
