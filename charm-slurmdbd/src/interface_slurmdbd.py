#! /usr/bin/env python3
"""Slurmdbd."""
import json
import logging


from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
    StoredState,
)


logger = logging.getLogger()


class SlurmdbdAvailableEvent(EventBase):
    """Emitted when slurmdbd is available."""


class SlurmdbdUnAvailableEvent(EventBase):
    """Emitted when slurmdbd is unavailable."""


class MungeKeyAvailableEvent(EventBase):
    """Emitted when the munge key becomes available."""


class SlurmdbdEvents(ObjectEvents):
    """Slurmdbd relation events."""

    munge_key_available = EventSource(MungeKeyAvailableEvent)
    slurmdbd_available = EventSource(SlurmdbdAvailableEvent)
    slurmdbd_unavailable = EventSource(SlurmdbdUnAvailableEvent)


class Slurmdbd(Object):
    """Slurmdbd."""

    on = SlurmdbdEvents()

    _stored = StoredState()

    def __init__(self, charm, relation_name):
        """Observe relation lifecycle events."""
        super().__init__(charm, relation_name)

        self._charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_changed(self, event):
        app_relation_data = event.relation.data.get(event.app)
        # Check for the existence of the app in the relation data
        # defer if not exists.
        if not app_relation_data:
            event.defer()
            return

        munge_key = app_relation_data.get('munge_key')
        # Check for the existence of the munge key in the relation data
        # defer if not exists.
        if not munge_key:
            event.defer()
            return

        self._charm.set_munge_key(munge_key)
        self.on.slurmdbd_available.emit()

    def _on_relation_broken(self, event):
        self.set_slurmdbd_info_on_app_relation_data("")
        self.on.slurmdbd_unavailable.emit()

    def set_slurmdbd_info_on_app_relation_data(self, slurmdbd_info):
        """Set slurmdbd_info."""
        relations = self.framework.model.relations['slurmdbd']
        # Iterate over each of the relations setting the relation data.
        for relation in relations:
            if slurmdbd_info != "":
                relation.data[self.model.app]['slurmdbd_info'] = json.dumps(
                    slurmdbd_info
                )
            else:
                relation.data[self.model.app]['slurmdbd_info'] = ""
