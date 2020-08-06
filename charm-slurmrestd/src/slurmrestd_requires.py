#!/usr/bin/python3
"""SlurmrestdRequiries."""
import json
import logging


from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


logger = logging.getLogger()


class SlurmctldAvailableEvent(EventBase):
    """SlurmctldAvailableEvent."""


class SlurmctldUnavailableEvent(EventBase):
    """SlurmctldUnavailableEvent."""


class SlurmLoginEvents(ObjectEvents):
    """SlurmLoginEvents."""

    slurmctld_available = EventSource(SlurmctldAvailableEvent)
    slurmctld_unavailable = EventSource(SlurmctldUnavailableEvent)


class SlurmrestdRequires(Object):
    """SlurmrestdRequires."""

    on = SlurmLoginEvents()

    def __init__(self, charm, relation_name):
        """Set the provides initial data."""
        super().__init__(charm, relation_name)
        self.charm = charm

        self.framework.observe(
            charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            charm.on[relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_changed(self, event):
        slurmctld_acquired = self.charm.is_slurmctld_available()
        # this happens when data changes on the relation
        slurm_config = event.relation.data[event.app].get("slurm_config", None)
        if slurm_config:
            if not slurmctld_acquired:
                self.charm.set_slurmctld_available(True)
            self.charm.set_slurm_config(json.loads(slurm_config))
            self.on.slurmctld_available.emit()

    def _on_relation_broken(self, event):
        self.charm.set_slurmctld_available(False)
        self.on.slurmctld_unavailable.emit()
