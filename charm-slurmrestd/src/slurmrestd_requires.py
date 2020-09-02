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


class MungeKeyAvailableEvent(EventBase):
    """MungeKeyAvailableEvent."""


class SlurmrestdEvents(ObjectEvents):
    """SlurmLoginEvents."""

    slurmctld_available = EventSource(SlurmctldAvailableEvent)
    slurmctld_unavailable = EventSource(SlurmctldUnavailableEvent)
    munge_key_available = EventSource(MungeKeyAvailableEvent)


class SlurmrestdRequires(Object):
    """SlurmrestdRequires."""

    on = SlurmrestdEvents()

    def __init__(self, charm, relation_name):
        """Set the provides initial data."""
        super().__init__(charm, relation_name)
        self.charm = charm

        self.framework.observe(
            charm.on[relation_name].relation_joined,
            self._on_relation_joined
        )
        self.framework.observe(
            charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            charm.on[relation_name].relation_broken,
            self._on_relation_broken
        )

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

    def _on_relation_changed(self, event):
        app_relation_data = event.relation.data.get(event.app)
        if not app_relation_data:
            event.defer()
            return

        slurm_config = app_relation_data.get("slurm_config")
        if not slurm_config:
            event.defer()
            return

        slurmctld_acquired = self.charm.is_slurmctld_available()
        if not slurmctld_acquired:
            self.charm.set_slurmctld_available(True)

        self.charm.set_slurm_config(json.loads(slurm_config))
        self.on.slurmctld_available.emit()

    def _on_relation_broken(self, event):
        self.charm.set_slurmctld_available(False)
        self.on.slurmctld_unavailable.emit()
