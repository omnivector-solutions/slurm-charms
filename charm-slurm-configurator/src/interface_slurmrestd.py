#!/usr/bin/python3
"""SlurmrestdProvides."""
import logging
import json

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


logger = logging.getLogger()


class SlurmrestdAvailableEvent(EventBase):
    """Emmited when slurmrestd is available."""


class SlurmrestdUnAvailableEvent(EventBase):
    """Emmited when the slurmrestd relation is broken."""


class SlurmrestdEvents(ObjectEvents):
    """SlurmrestdEvents."""

    slurmrestd_available = EventSource(SlurmrestdAvailableEvent)
    slurmrestd_unavailable = EventSource(SlurmrestdUnAvailableEvent)


class Slurmrestd(Object):
    """Slurmrestd interface."""

    on = SlurmrestdEvents()

    def __init__(self, charm, relation_name):
        """Set the initial data."""
        super().__init__(charm, relation_name)

        self.charm = charm
        self.framework.observe(
            charm.on[relation_name].relation_created,
            self._on_relation_created
        )
        self.framework.observe(
            charm.on[relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_created(self, event):
        self.charm.set_slurmrestd_available(True)
        self.on.slurmrestd_available.emit()

    def _on_relation_broken(self, event):
        self.charm.set_slurmrestd_available(False)
        self.on.slurmrestd_unavailable.emit()

    def set_slurm_config_on_app_relation_data(
        self,
        slurm_config,
    ):
        """Set the slurm_conifg to the app data on the relation.

        Setting data on the relation forces the units of related applications
        to observe the relation-changed event so they can acquire and
        render the updated slurm_config.
        """
        relations = self.charm.framework.model.relations['slurmrestd']
        for relation in relations:
            app_relation_data = relation.data[self.model.app]
            app_relation_data['slurm_config'] = json.dumps(slurm_config)
