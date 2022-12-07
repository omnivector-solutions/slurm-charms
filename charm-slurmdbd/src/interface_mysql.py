#!/usr/bin/env python3
"""MySqlRequires."""
import logging

from ops.framework import EventBase, EventSource, Object, ObjectEvents

logger = logging.getLogger()


class DatabaseAvailableEvent(EventBase):
    """DatabaseAvailableEvent."""


class DatabaseUnavailableEvent(EventBase):
    """DatabaseAvailableEvent."""


class DatabaseEvents(ObjectEvents):
    """Slurmdbd database events."""

    database_available = EventSource(DatabaseAvailableEvent)
    database_unavailable = EventSource(DatabaseUnavailableEvent)


class MySQLClient(Object):
    """Mysql Client Interface."""

    on = DatabaseEvents()

    def __init__(self, charm, relation_name):
        """Observe relation_changed."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name
        # Observe the relation-changed hook event and bind
        # self.on_relation_changed() to handle the event.
        self.framework.observe(
            self._charm.on[self._relation_name].relation_joined,
            self._on_relation_joined,
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed,
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_departed,
            self._on_relation_departed,
        )

    @property
    def is_joined(self) -> bool:
        """Return wether the relation was created."""
        if self._charm.framework.model.relations.get(self._relation_name):
            return True
        else:
            return False

    @property
    def _relation(self):
        """Return the Relation object for this relation."""
        return self.framework.model.get_relation(self._relation_name)

    def _on_relation_joined(self, event):
        self._relation.data[self.model.unit]["database"] = "slurm" # Store this in a different place
        self._relation.data[self.model.unit]["username"] = "slurm" # Store this in a different place
        self._relation.data[self.model.unit]["hostname"] = "%"

    def _on_relation_changed(self, event):
        """Get the database password and set the db_info.

        This relation is responsible for getting the database password
        from the mysql-router and setting the information to stored state.
        """
        event_unit_data = event.relation.data.get(event.unit)
        if not event_unit_data:
            event.defer()
            return

        password = event_unit_data.get("password")

        if password:
            self._charm.set_db_info(
                {
                    "db_username": "slurm", # Need to store this in a better place
                    "db_password": password,
                    "db_hostname": "127.0.0.1",
                    "db_port": "3306",
                    "db_name": "slurm", # Need to store this in a better place
                }
            )
            self.on.database_available.emit()
        else:
            logger.info("DB INFO NOT AVAILABLE")
            event.defer()
            return

    def _on_relation_departed(self, event):
        self.on.database_unavailable.emit()
