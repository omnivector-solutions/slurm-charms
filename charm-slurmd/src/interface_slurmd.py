#!/usr/bin/env python3
"""Slurmd."""
import json
import logging

from ops.framework import (
    EventBase, EventSource, Object, ObjectEvents, StoredState,
)

logger = logging.getLogger(__name__)


class SlurmctldAvailableEvent(EventBase):
    """Emitted when slurmctld is available."""


class SlurmctldUnavailableEvent(EventBase):
    """Emit when the relation to slurmctld is broken."""


class MungeKeyAvailableEvent(EventBase):
    """Emit when the munge key has been acquired and set to the charm state."""


class SlurmdEvents(ObjectEvents):
    """Slurmd emitted events."""

    munge_key_available = EventSource(MungeKeyAvailableEvent)
    slurmctld_available = EventSource(SlurmctldAvailableEvent)
    slurmctld_unavailable = EventSource(SlurmctldUnavailableEvent)


class Slurmd(Object):
    """Slurmd."""

    _stored = StoredState()
    on = SlurmdEvents()

    def __init__(self, charm, relation_name):
        """Set initial data and observe interface events."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self._stored.set_default(
            slurm_config=dict(),
            munge_key=str(),
            restart_slurmd_uuid=str(),
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_created,
            self._on_relation_created,
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_joined,
            self._on_relation_joined,
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed,
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken,
        )

    def _on_relation_created(self, event):
        """Handle the relation-created event.

        Set the partition_name on the application relation data.
        """
        partition_name = self._charm.get_partition_name()
        if not partition_name:
            event.defer()
            return

        if self.framework.model.unit.is_leader():
            event.relation.data[self.model.app]["partition_name"] = \
                partition_name

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

        # Store the munge_key in the charm's state
        self._store_munge_key(munge_key)
        self.on.munge_key_available.emit()
        self.on.slurmctld_available.emit()


    def _on_relation_changed(self, event):
        """Check for the munge_key in the relation data."""
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            return

        munge_key = event_app_data.get('munge_key')


        if not munge_key:
            return

        # Store the munge_key in the interface StoredState if it has changed
        if munge_key != self.get_stored_munge_key():
            self._store_munge_key(munge_key)
            self.on.munge_key_available.emit()

    def _on_relation_broken(self, event):
        self.on.slurmctld_unavailable.emit()

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    @property
    def num_relations(self):
        """Return the number of relations."""
        return len(self._charm.framework.model.relations["slurmd"])

    @property
    def is_joined(self):
        """Return True if relation is joined."""
        return self.num_relations > 0

    def set_partition_info_on_app_relation_data(self, partition_info):
        """Set the slurmd partition on the app relation data.

        Setting data on the application relation forces the units of related
        slurm-configurator application(s) to observe the relation-changed
        event so they can acquire and redistribute the updated slurm config.
        """
        relations = self._charm.framework.model.relations["slurmd"]
        for relation in relations:
            relation.data[self.model.app]["partition_info"] = json.dumps(
                partition_info
            )

    def _store_munge_key(self, munge_key):
        self._stored.munge_key = munge_key

    def get_stored_munge_key(self):
        """Retrieve the munge_key from the StoredState."""
        return self._stored.munge_key

    def _store_slurm_config(self, slurm_config):
        self._stored.slurm_config = slurm_config

    def get_stored_slurm_config(self):
        """Retrieve the slurm_config from the StoredState."""
        return self._stored.slurm_config

    def _store_slurmd_restart_uuid(self, restart_slurmd_uuid):
        self._stored.restart_slurmd_uuid = restart_slurmd_uuid

    def _get_slurmd_restart_uuid(self):
        return self._stored.restart_slurmd_uuid
