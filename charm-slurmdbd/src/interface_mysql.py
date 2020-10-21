#!/usr/bin/env python3
"""MySqlRequires."""
import logging

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


logger = logging.getLogger()


class DatabaseAvailableEvent(EventBase):
    """DatabaseAvailableEvent."""


class DatabaseEvents(ObjectEvents):
    """Slurmdbd database events."""

    database_available = EventSource(DatabaseAvailableEvent)


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
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

    def _on_relation_changed(self, event):
        event_unit_data = event.relation.data.get(event.unit)
        if not event_unit_data:
            event.defer()
            return

        user = event_unit_data.get('user')
        password = event_unit_data.get('password')
        host = event_unit_data.get('host')
        database = event_unit_data.get('database')

        if (user and password and host and database):
            self._charm.set_db_info({
                'db_username': user,
                'db_password': password,
                'db_hostname': host,
                'db_port': "3306",
                'db_name': database,
            })
            self.on.database_available.emit()
        else:
            logger.info("DB INFO NOT AVAILABLE")
            event.defer()
            return
