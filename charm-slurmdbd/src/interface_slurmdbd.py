#! /usr/bin/env python3
"""Slurmdbd."""
import json
import logging

from ops.framework import (
    EventBase, EventSource, Object, ObjectEvents, StoredState,
)


logger = logging.getLogger()


class SlurmdbdAvailableEvent(EventBase):
    """Emitted when slurmdbd is available."""


class SlurmConfiguratorUnAvailableEvent(EventBase):
    """Emitted when slurm-configurator is unavailable."""


class SlurmConfiguratorAvailableEvent(EventBase):
    """Emitted when slurm-configurator joins the relation."""


class SlurmdbdEvents(ObjectEvents):
    """Slurmdbd relation events."""

    slurm_configurator_available = EventSource(SlurmConfiguratorAvailableEvent)
    slurm_configurator_unavailable = EventSource(
        SlurmConfiguratorUnAvailableEvent
    )
    slurmdbd_available = EventSource(SlurmdbdAvailableEvent)


class Slurmdbd(Object):
    """Slurmdbd."""

    _stored = StoredState()
    on = SlurmdbdEvents()

    def __init__(self, charm, relation_name):
        """Observe relation lifecycle events."""
        super().__init__(charm, relation_name)

        self._charm = charm
        self._relation_name = relation_name

        self._stored.set_default(
            munge_key=str(),
            jwt_key=str(),
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_joined,
            self._on_relation_joined,
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken,
        )

    def _on_relation_joined(self, event):
        """Handle the relation-joined event.

        Get the munge_key from slurm-configurator and save it to the
        charm stored state.
        """
        # Since we are in relation-joined (with the app on the other side)
        # we can almost guarantee that the app object will exist in
        # the event, but check for it just in case.
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            event.defer()
            return

        # slurm-configurator sets the munge_key on the relation-created event
        # which happens before relation-joined. We can almost guarantee that
        # the munge key will exist at this point, but check for it just incase.
        munge_key = event_app_data.get("munge_key")
        if not munge_key:
            event.defer()
            return

        # slurm-configurator sets the jwt_rsa on the relation-created event
        # which happens before relation-joined. We can almost guarantee that
        # the jwt_rsa will exist at this point, but check for it just incase.
        jwt_rsa = event_app_data.get("jwt_rsa")
        if not jwt_rsa:
            event.defer()
            return

        # Store the munge_key and jwt_rsa in the interface's stored state
        # object and emit the slurm_configurator_available event.
        self._store_munge_key(munge_key)
        self._store_jwt_rsa(jwt_rsa)
        self.on.slurm_configurator_available.emit()

    def _on_relation_broken(self, event):
        """Clear the application relation data and emit the event."""
        self.set_slurmdbd_info_on_app_relation_data("")
        self.on.slurm_configurator_unavailable.emit()

    def set_slurmdbd_info_on_app_relation_data(self, slurmdbd_info):
        """Send slurmdbd_info to slurm-configurator."""
        relations = self.framework.model.relations["slurmdbd"]
        # Iterate over each of the relations setting the relation data.
        for relation in relations:
            if slurmdbd_info != "":
                relation.data[self.model.app]["slurmdbd_info"] = json.dumps(
                    slurmdbd_info
                )
            else:
                relation.data[self.model.app]["slurmdbd_info"] = ""

    def _store_munge_key(self, munge_key):
        """Set the munge key in the stored state."""
        self._stored.munge_key = munge_key

    def get_munge_key(self):
        """Retrieve the munge key from the stored state."""
        return self._stored.munge_key

    def _store_jwt_rsa(self, jwt_rsa):
        """Store the jwt_rsa in the interface stored state."""
        self._stored.jwt_rsa = jwt_rsa

    def get_jwt_rsa(self):
        """Retrieve the jwt_rsa from stored state."""
        return self._stored.jwt_rsa
