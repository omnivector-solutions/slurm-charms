#!/usr/bin/python3
"""AcctGather (Influxdb) interface."""
import json
import logging
import random

import influxdb
from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
    StoredState,
)

logger = logging.getLogger()


class InfluxDBAvailableEvent(EventBase):
    """InfluxDBAvailable event."""


class InfluxDBUnAvailableEvent(EventBase):
    """InfluxDBUnAvailable event."""


class InfluxDBEvents(ObjectEvents):
    """InfluxDBEvents."""

    influxdb_available = EventSource(InfluxDBAvailableEvent)
    influxdb_unavailable = EventSource(InfluxDBUnAvailableEvent)


def random_string(length=10):
    """Generate a random string."""
    random_str = ""
    for i in range(length):
        random_integer = random.randint(97, 97 + 26 - 1)
        flip_bit = random.randint(0, 1)
        random_integer = \
            random_integer - 32 if flip_bit == 1 else random_integer
        random_str += (chr(random_integer))
    return random_str


class InfluxDB(Object):
    """InfluxDB interface."""

    _stored = StoredState()
    on = InfluxDBEvents()

    _INFLUX_USER = 'slurm'
    _INFLUX_DATABASE = 'slurm'
    _INFLUX_PRIVILEGE = 'all'

    def __init__(self, charm, relation_name):
        """Observe relation events."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self._stored.set_default(
            influxdb_info=str(),
            influxdb_admin_info=str(),
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_changed(self, event):
        """Store influxdb_ingress in the charm."""
        if self.framework.model.unit.is_leader():
            if not self._stored.influxdb_admin_info:
                ingress = event.relation.data[event.unit]['ingress-address']
                port = event.relation.data[event.unit].get('port')
                user = event.relation.data[event.unit].get('user')
                password = event.relation.data[event.unit].get('password')

                if all([ingress, port, user, password]):
                    self._stored.influxdb_admin_info = json.dumps({
                        'ingress': ingress,
                        'port': port,
                        'user': user,
                        'password': password,
                    })

                    # Influxdb client
                    client = influxdb.InfluxDBClient(
                        ingress,
                        port,
                        user,
                        password,
                    )

                    # Influxdb slurm user password
                    influx_slurm_password = random_string()

                    # Only create the user and db if they don't already exist
                    users = [
                        db['user']
                        for db in client.get_list_users()
                    ]
                    if self._INFLUX_USER not in users:
                        client.create_user(
                            self._INFLUX_DATABASE,
                            influx_slurm_password
                        )

                    databases = [
                        db['name']
                        for db in client.get_list_database()
                    ]
                    if self._INFLUX_DATABASE not in databases:
                        client.create_database(self._INFLUX_DATABASE)

                    client.grant_privilege(
                        self._INFLUX_PRIVILEGE,
                        self._INFLUX_DATABASE,
                        self._INFLUX_USER
                    )

                    # Dump influxdb_info to json and set it to state
                    self._stored.influxdb_info = json.dumps(
                        {
                            'ingress': ingress,
                            'port': port,
                            'user': self._INFLUX_USER,
                            'password': influx_slurm_password,
                            'database': self._INFLUX_DATABASE,
                        }
                    )
                    self.on.influxdb_available.emit()

    def _on_relation_broken(self, event):
        """Remove the database and user from influxdb."""
        if self.framework.model.unit.is_leader():
            if self._stored.influxdb_admin_info:
                influxdb_admin_info = json.loads(
                    self._stored.influxdb_admin_info
                )

                client = influxdb.InfluxDBClient(
                    influxdb_admin_info['ingress'],
                    influxdb_admin_info['port'],
                    influxdb_admin_info['user'],
                    influxdb_admin_info['password'],
                )
                databases = [
                    db['name']
                    for db in client.get_list_database()
                ]
                if self._INFLUX_DATABASE in databases:
                    client.drop_database(self._INFLUX_DATABASE)

                users = [
                    db['user']
                    for db in client.get_list_users()
                ]
                if self._INFLUX_USER in users:
                    client.drop_user(self._INFLUX_USER)

                self._stored.influxdb_info = ""
                self._stored.influxdb_admin_info = ""
                self.on.influxdb_unavailable.emit()

    def get_influxdb_info(self):
        """Return the influxdb info."""
        influxdb_info = self._stored.influxdb_info
        if influxdb_info:
            return json.loads(influxdb_info)
        else:
            return None
