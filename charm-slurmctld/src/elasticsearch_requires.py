#!/usr/bin/python3
"""ElasticsearchRequires."""
from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


class ElasticsearchAvailableEvent(EventBase):
    """ElasticsearchAvailable event."""

    pass


class ElasticsearchEvents(ObjectEvents):
    """ElasticsearchEvents."""

    elasticsearch_available = EventSource(ElasticsearchAvailableEvent)


class ElasticsearchRequires(Object):
    """Connect Slurmctld to elasticsearch."""

    on = ElasticsearchEvents()

    def __init(self, charm, relation_name):
        """Initialize the class."""
        super().__init__(charm, relation_name)

        self.charm = charm
        self.framework.observe(
            charm.on[self._relation_name].relation_created,
            self._on_relation_created
        )
        self.framework.observe(
            charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

        def _on_relation_changed(self, event):
            host = event.relation.data[event.unit].get('hostname', None)
            self.charm.set_elasticsearch_endpoint(f"http://{host}:9200")
            self.on.elasticsearch_available.emit()
