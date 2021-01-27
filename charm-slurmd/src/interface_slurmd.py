#!/usr/bin/python3
"""Slurmd."""
import json

from ops.framework import EventBase, EventSource, Object, ObjectEvents


class SlurmConfigAvailableEvent(EventBase):
    """Emitted when slurm config is available."""


class MungeKeyAvailableEvent(EventBase):
    """Emit when the munge key has been acquired and set to the charm state."""


class SlurmdProvidesEvents(ObjectEvents):
    """SlurmctldProvidesEvents."""

    slurm_config_available = EventSource(SlurmConfigAvailableEvent)
    munge_key_available = EventSource(MungeKeyAvailableEvent)


class Slurmd(Object):
    """Slurmd."""

    on = SlurmdProvidesEvents()

    def __init__(self, charm, relation_name):
        """Set initial data and observe interface events."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            self._charm.on[self._relation_name].relation_created,
            self._on_relation_created,
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_joined,
            self._on_relation_joined,
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
        if self.framework.model.unit.is_leader():
            if not partition_name:
                event.defer()
                return

            event.relation.data[self.model.app][
                "partition_name"
            ] = self._charm.get_partition_name()

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
        self._charm.set_munge_key(munge_key)
        self.on.munge_key_available.emit()

    def _on_relation_broken(self, event):
        self.on.slurm_config_available.emit()

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    @property
    def is_joined(self):
        """Return True if relation is joined."""
        return self._relation is not None

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

    def get_slurm_config(self):
        """Return slurm_config."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                app_data = self._relation.data.get(app)
                if app_data:
                    slurm_config = app_data.get("slurm_config")
                    if slurm_config:
                        return json.loads(slurm_config)
        return None
