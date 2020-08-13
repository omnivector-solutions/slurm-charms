#!/usr/bin/python3
"""Elasticserch interface."""
import logging

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)

logger = logging.getLogger()


class ElasticsearchAvailableEvent(EventBase):
    """ElasticsearchAvailable event."""


class ElasticsearchEvents(ObjectEvents):
    """ElasticsearchEvents."""

    elasticsearch_available = EventSource(ElasticsearchAvailableEvent)


class ElasticsearchRequires(Object):
    """Require side of elasticsearch interface."""

    on = ElasticsearchEvents()

    def __init__(self, charm, relation_name):
        """Observe relation changed."""
        super().__init__(charm, relation_name)
        self.charm = charm
        self.framework.observe(
            charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )

    def _on_relation_changed(self, event):
        """Get relation data from provides."""
        ingress = event.relation.data[event.unit]['ingress-address']
        logger.debug(f'ingress address: {ingress}')
        self.charm._stored.elasticsearch_ingress = f'http://{ingress}:9200'
        self.on.elasticsearch_available.emit()
