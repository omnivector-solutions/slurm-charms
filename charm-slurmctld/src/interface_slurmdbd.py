#!/usr/bin/env python3
"""Slurmdbd."""
import json
import logging

from ops.framework import EventBase, EventSource, Object, ObjectEvents


logger = logging.getLogger()


class SlurmdbdAvailableEvent(EventBase):
    """Emits slurmdbd_available."""


class SlurmdbdUnavailableEvent(EventBase):
    """Emits slurmdbd_unavailable."""


class SlurmdbdAvailableEvents(ObjectEvents):
    """SlurmdbdAvailableEvents."""

    slurmdbd_available = EventSource(SlurmdbdAvailableEvent)
    slurmdbd_unavailable = EventSource(SlurmdbdUnavailableEvent)


class Slurmdbd(Object):
    """Facilitate slurmdbd lifecycle events."""

    on = SlurmdbdAvailableEvents()

    def __init__(self, charm, relation_name):
        """Set the initial attribute values for this interface."""
        super().__init__(charm, relation_name)

        self._charm = charm
        self._relation_name = relation_name


        self.framework.observe(
            self._charm.on[self._relation_name].relation_created,
            self._on_relation_created,
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed,
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_departed,
            self._on_relation_departed,
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken,
        )
        logger.debug(f"######### ON_INSTALL: {self.on.__dict__}")


    def _on_relation_created(self, event):
        """Perform relation-created event operations."""
        # Check that slurm has been installed so that we know the munge key is
        # available. Defer if slurm has not been installed yet.
        if not self._charm.is_slurm_installed():
            event.defer()
            return

        # Get the munge_key and set it to the application relation data,
        # to be retrieved on the other side by slurmdbd.
        munge_key = self._charm.get_munge_key()
        event.relation.data[self.model.app]["munge_key"] = munge_key

        # Get the jwt_rsa key from the slurm_ops_manager and set it to the app
        # data on the relation to be retrieved on the other side by slurmdbd.
        jwt_rsa = self._charm.get_jwt_rsa()
        event.relation.data[self.model.app]["jwt_rsa"] = jwt_rsa

    def _on_relation_changed(self, event):
        event_app_data = event.relation.data.get(event.app)
        if event_app_data:
            slurmdbd_info = event_app_data.get("slurmdbd_info")
            if slurmdbd_info:
                self.on.slurmdbd_available.emit()

    def _on_relation_departed(self, event):
        self.on.slurmdbd_unavailable.emit()

    def _on_relation_broken(self, event):
        if self.framework.model.unit.is_leader():
            event.relation.data[self.model.app]["munge_key"] = ""
            event.relation.data[self.model.app]["jwt_rsa"] = ""
        self.on.slurmdbd_unavailable.emit()

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    def get_slurmdbd_info(self):
        """Return the slurmdbd_info."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                app_data = relation.data.get(app)
                if app_data:
                    slurmdbd_info = app_data.get("slurmdbd_info")
                    if slurmdbd_info:
                        return json.loads(slurmdbd_info)
        return None
