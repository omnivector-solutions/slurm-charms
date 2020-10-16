#!/usr/bin/python3
"""Grafana Source Interface."""
import logging

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
    StoredState,
)


logger = logging.getLogger()


class GrafanaSourceAvailableEvent(EventBase):
    """GrafanaSourceAvailable event."""


class GrafanaSourceEvents(ObjectEvents):
    """GrafanaSourceEvents."""

    grafana_available = EventSource(GrafanaSourceAvailableEvent)


class GrafanaSource(Object):
    """Grafana Source Interface."""

    _stored = StoredState()
    on = GrafanaSourceEvents()

    def __init__(self, charm, relation_name):
        """Observe relation events."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self._stored.set_default(grafana_source_created=False)

        self.framework.observe(
            self._charm.on[self._relation_name].relation_joined,
            self._on_relation_joined
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_joined(self, event):
        if self.framework.model.unit.is_leader():
            self.on.grafana_available.emit()

    def _on_relation_broken(self, event):
        if self.framework.model.unit.is_leader():
            app_relation_data = self._relation.data[self.model.app]
            app_relation_data['url'] = ""
            app_relation_data['username'] = ""
            app_relation_data['password'] = ""
            app_relation_data['database'] = ""
            self._stored.grafana_source_created = False

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    @property
    def is_joined(self):
        """Return True if self._relation is not None."""
        return self._relation is not None

    def set_grafana_source_info(self, influxdb):
        """Set grafana source info on relation."""
        if self.framework.model.unit.is_leader():
            app_relation_data = self._relation.data[self.model.app]
            app_relation_data['type'] = 'influxdb'
            app_relation_data['url'] = \
                f"{influxdb['ingress']}:{influxdb['port']}"
            app_relation_data['username'] = influxdb['user']
            app_relation_data['password'] = influxdb['password']
            app_relation_data['database'] = influxdb['database']
            self._stored.grafana_source_created = True
