#! /usr/bin/env python3
"""SlurmdbdProvidesRelation."""
import logging
import socket


from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


logger = logging.getLogger()


class SlurmctldAvailableEvent(EventBase):
    """Emitted when slurmctld is available."""


class SlurmctldUnAvailableEvent(EventBase):
    """Emitted when slurmctld is unavailable."""


class MungeKeyAvailableEvent(EventBase):
    """Emitted when the munge key becomes available."""


class SlurmdbdProvidesRelationEvents(ObjectEvents):
    """SlurmdbdProvidesRelationEvents."""

    munge_key_available = EventSource(MungeKeyAvailableEvent)
    slurmctld_available = EventSource(SlurmctldAvailableEvent)
    slurmctld_unavailable = EventSource(SlurmctldUnAvailableEvent)


class SlurmdbdProvidesRelation(Object):
    """SlurmdbdProvidesRelation."""

    on = SlurmdbdProvidesRelationEvents()

    def __init__(self, charm, relation_name):
        """Set the provides initial data."""
        super().__init__(charm, relation_name)

        self.charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            charm.on[self._relation_name].relation_joined,
            self._on_relation_joined
        )
        self.framework.observe(
            charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            charm.on[self._relation_name].relation_broken,
            self._on_relation_broken
        )

    def set_slurmdbd_available_on_unit_relation_data(self):
        """Set slurmdbd_available."""
        slurmdbd_relations = self.framework.model.relations['slurmdbd']
        # Iterate over each of the relations setting the relation data.
        for relation in slurmdbd_relations:
            relation.data[self.model.unit]['slurmdbd_available'] = "true"

    def _on_relation_joined(self, event):
        if not event.relation.data.get(event.app):
            event.defer()
            return

        munge_key = event.relation.data[event.app].get('munge_key')
        if not munge_key:
            event.defer()
            return

        self.charm.set_munge_key(munge_key)
        self.on.munge_key_available.emit()

        event.relation.data[self.model.unit]['hostname'] = \
            socket.gethostname().split(".")[0]
        event.relation.data[self.model.unit]['port'] = "6819"

    def _on_relation_changed(self, event):
        self._on_relation_joined(event)

    def _on_relation_broken(self, event):
        """Emit the slurmctld_unavailable event when the relation is broken."""
        self.on.slurmctld_unavailable.emit()
