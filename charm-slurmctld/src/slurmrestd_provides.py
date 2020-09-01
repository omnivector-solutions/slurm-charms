#!/usr/bin/python3
"""SlurmrestdProvides."""
import logging


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


class SlurmrestdProvidesEvents(ObjectEvents):
    """SlurmrestdProvidesEvents."""

    slurmrestd_available = EventSource(SlurmrestdAvailableEvent)
    slurmrestd_unavailable = EventSource(SlurmrestdUnAvailableEvent)


class SlurmrestdProvides(Object):
    """Slurmrestd Provides Relation."""

    on = SlurmrestdProvidesEvents()

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
        # Check that slurm has been installed so that we know the munge key is
        # available. Defer if slurm has not been installed yet.
        if not self.charm.is_slurm_installed():
            event.defer()
            return
        # Get the munge_key from the slurm_ops_manager and set it to the app
        # data on the relation to be retrieved on the other side by slurmdbd.
        munge_key = self.charm.get_munge_key()
        event.relation.data[self.model.app]['munge_key'] = munge_key

        self.charm.set_slurmrestd_available(True)
        self.on.slurmrestd_available.emit()

    def _on_relation_broken(self, event):
        self.charm.set_slurmrestd_available(False)
        self.on.slurmrestd_unavailable.emit()
