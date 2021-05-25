#!/usr/bin/env python3
"""SlurmrestdProvides."""
import json
import logging
import uuid

from ops.framework import EventBase, EventSource, Object, ObjectEvents

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

        self._charm = charm
        self.framework.observe(
            self._charm.on[relation_name].relation_created,
            self._on_relation_created
        )
        self.framework.observe(
            self._charm.on[relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_created(self, event):
        # Check that slurm has been installed so that we know the munge key is
        # available. Defer if slurm has not been installed yet.
        if not self._charm.is_slurm_installed():
            event.defer()
            return

        # Get the munge_key from the slurm_ops_manager and set it to the app
        # data on the relation to be retrieved on the other side by slurmdbd.
        app_relation_data = event.relation.data[self.model.app]
        app_relation_data["munge_key"] = self._charm.get_munge_key()
        app_relation_data["jwt_rsa"] = self._charm.get_jwt_rsa()
        self._charm.set_slurmrestd_available(True)
        self.on.slurmrestd_available.emit()

    def _on_relation_broken(self, event):
        self._charm.set_slurmrestd_available(False)
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
        relations = self._charm.framework.model.relations["slurmrestd"]
        for relation in relations:
            app_relation_data = relation.data[self.model.app]
            app_relation_data["slurm_config"] = json.dumps(slurm_config)

    def restart_slurmrestd(self):
        """Send a restart signal to related slurmd applications."""
        relations = self._charm.framework.model.relations["slurmrestd"]
        for relation in relations:
            app_relation_data = relation.data[self.model.app]
            app_relation_data["restart_slurmrestd_uuid"] = str(uuid.uuid4())
