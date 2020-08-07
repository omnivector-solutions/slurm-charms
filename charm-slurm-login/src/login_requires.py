#! /usr/bin/env python3
"""SlurmdbdProvidesRelation."""
import logging
import json
from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)
from ops.model import BlockedStatus



logger = logging.getLogger()


class ConfigAvailableEvents(EventBase):
    logger.debug("config available event emmitted ######")

class LoginEvents(ObjectEvents):
    config_available = EventSource(ConfigAvailableEvents)


class LoginRequires(Object):
    """SlurmdbdProvidesRelation."""

    on = LoginEvents()
    def __init__(self, charm, relation_name):
        """Set the provides initial data."""
        super().__init__(charm, relation_name)
        self.charm = charm
        self.framework.observe(
            charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            charm.on[relation_name].relation_joined,
            self._on_relation_joined
        )

    def _on_relation_joined(self, event):
        self.charm.unit.status = BlockedStatus("need to add-unit slurmd")

    def _on_relation_changed(self, event):
        # this event should go off when a slurmd node is added to the cluster
        added_config = event.relation.data[event.app].get("slurm_config", None)
        if added_config:
            self.charm._stored.slurm_config = json.loads(added_config)
            self.on.config_available.emit()
