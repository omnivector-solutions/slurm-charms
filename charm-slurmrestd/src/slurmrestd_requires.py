#!/usr/bin/python3
"""SlurmdbdProvidesRelation."""
import json
import logging


from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)
from ops.model import BlockedStatus


logger = logging.getLogger()


class ConfigAvailableEvent(EventBase):
    """ConfigAvailableEvent."""


class LoginEvents(ObjectEvents):
    """SlurmLoginEvents."""

    config_available = EventSource(ConfigAvailableEvent)


class RestdRequires(Object):
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
        self.framework.observe(
            charm.on[relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_joined(self, event):
        self.charm.unit.status = BlockedStatus("need to add-unit slurmd")

    def _on_relation_changed(self, event):
        # this happens when data changes on the relation
        slurm_config = event.relation.data[event.app].get("slurm_config", None)
        if slurm_config:
            self.charm.set_slurm_config(json.loads(slurm_config))
            self.on.config_available.emit()

    def _on_relation_broken(self, event):
        self.charm.unit.status = BlockedStatus("need relation to slurmctld")
