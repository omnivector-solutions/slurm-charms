#!/usr/bin/python3
"""ElasticsearchRequires."""
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
    """Connect Slurmctld to elasticsearch."""
    on = ElasticsearchEvents()
    
    def __init(self, charm, relation_name):
        """set the provide relation data"""
        super().__init__(charm, relation_name)

        self.framework.observe(
            charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )

        def _on_relation_changed(self, event):
            host = event.relation.data[event.unit].get('hostname', None)
            self.charm._stored.elasticsearch_hostname = { 'elasticsearch_address': f"http://{host}:9200" }
            logger.debug("_________Inside RELATION CHANGED________________")
            logger.debug(host)
            self.on.elasticsearch_available.emit()
