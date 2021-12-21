#!/usr/bin/env python3
"""Elasticserch interface."""
import logging

from ops.framework import EventBase, EventSource, Object, ObjectEvents, StoredState

logger = logging.getLogger()


class ElasticsearchAvailableEvent(EventBase):
    """ElasticsearchAvailable event."""


class ElasticsearchUnAvailableEvent(EventBase):
    """ElasticsearchUnAvailable event."""


class ElasticsearchEvents(ObjectEvents):
    """ElasticsearchEvents."""
    elasticsearch_available = EventSource(ElasticsearchAvailableEvent)
    elasticsearch_unavailable = EventSource(ElasticsearchUnAvailableEvent)


class Elasticsearch(Object):
    """Elasticsearch interface."""

    _stored = StoredState()
    on = ElasticsearchEvents()

    def __init__(self, charm, relation_name):
        """Observe relation events."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self._stored.set_default(elasticsearch_host=str(),
                                 elasticsearch_port=str())

        self.framework.observe(self._charm.on[self._relation_name].relation_changed,
                               self._on_relation_changed)

        self.framework.observe(self._charm.on[self._relation_name].relation_broken,
                               self._on_relation_broken)

    def _on_relation_changed(self, event):
        """Get server address and store it."""
        ingress = event.relation.data[event.unit]["ingress-address"]
        self._stored.elasticsearch_host = ingress
        # elastic charm can't change the port, so hardcode it here
        self._stored.elasticsearch_port = "9200"
        self.on.elasticsearch_available.emit()

    def _on_relation_broken(self, event):
        """Clear elasticsearch_ingress and emit elasticsearch_unavailable."""
        self._stored.elasticsearch_ingress = ""
        self.on.elasticsearch_unavailable.emit()

    @property
    def elasticsearch_ingress(self) -> str:
        """Return elasticsearch_ingress."""
        host = self._stored.elasticsearch_host
        port = self._stored.elasticsearch_port
        if host:
            return f"http://{host}:{port}"
        else:
            return ""
