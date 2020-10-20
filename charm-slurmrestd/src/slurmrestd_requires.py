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


class SlurmrestdAvailableEvent(EventBase):
    """SlurmctldAvailableEvent."""


class SlurmrestdUnavailableEvent(EventBase):
    """SlurmctldUnavailableEvent."""


class SlurmrestdEvents(ObjectEvents):
    """SlurmLoginEvents."""

    config_available = EventSource(SlurmrestdAvailableEvent)
    config_unavailable = EventSource(SlurmrestdUnavailableEvent)


class SlurmrestdRequires(Object):
    """SlurmrestdRequires."""

    on = SlurmrestdEvents()

    def __init__(self, charm, relation_name):
        """Set the provides initial data."""
        super().__init__(charm, relation_name)
        self.charm = charm

        self._relation_name = relation_name


        self.framework.observe(
            charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            charm.on[relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_changed(self, event):
        """Check for the munge_key in the relation data."""
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            event.defer()
            return

        slurm_config = event_app_data.get('slurm_config')
        if not slurm_config:
            event.defer()
            return

        self.charm.set_config_available(True)
        self.on.config_available.emit()

    def _on_relation_broken(self, event):
        self.charm.set_config_available(False)
        self.on.config_available.emit()

    def get_slurm_config(self):
        """Return slurm_config."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                app_data = self._relation.data.get(app)
                if app_data:
                    slurm_config = app_data.get('slurm_config')
                    if slurm_config:
                        return json.loads(slurm_config)
        return None

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    @property
    def is_joined(self):
        """Return True if relation is joined."""
        return self._relation is not None
