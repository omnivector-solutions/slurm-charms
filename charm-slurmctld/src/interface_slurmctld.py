#!/usr/bin/python3
"""Slurmctld."""
import json
import logging

from ops.framework import EventBase, EventSource, Object, ObjectEvents

logger = logging.getLogger()


class SlurmConfiguratorAvailableEvent(EventBase):
    """Emitted when slurm-config is available."""


class SlurmConfiguratorUnAvailableEvent(EventBase):
    """Emitted when a slurmctld unit joins the relation."""


class MungeKeyAvailableEvent(EventBase):
    """Emitted when the munge key is acquired and saved."""


class SlurmctldRelationEvents(ObjectEvents):
    """Slurmctld relation events."""

    slurm_config_available = EventSource(
        SlurmConfiguratorAvailableEvent
    )
    slurm_configurator_unavailable = EventSource(
        SlurmConfiguratorUnAvailableEvent
    )
    munge_key_available = EventSource(
        MungeKeyAvailableEvent
    )


class Slurmctld(Object):
    """Slurmctld."""

    on = SlurmctldRelationEvents()

    def __init__(self, charm, relation_name):
        """Set initial data and observe interface events."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            self._charm.on[self._relation_name].relation_joined,
            self._on_relation_joined,
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

    def _on_relation_changed(self, event):
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            event.defer()
            return

        slurm_config = event_app_data.get("slurm_config")
        if not slurm_config:
            event.defer()
            return

        self.on.slurm_config_available.emit()

    def _on_relation_departed(self, event):
        self.on.slurm_configurator_unavailable.emit()

    def _on_relation_broken(self, event):
        self.set_slurmctld_info_on_app_relation_data("")
        self.on.slurm_configurator_unavailable.emit()

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    @property
    def is_joined(self):
        """Return True if self._relation is not None."""
        return self._relation is not None

    def set_slurmctld_info_on_app_relation_data(self, slurmctld_info):
        """Set slurmctld_info."""
        relations = self.framework.model.relations["slurmctld"]
        # Iterate over each of the relations setting the relation data.
        for relation in relations:
            if slurmctld_info != "":
                relation.data[self.model.app]["slurmctld_info"] = json.dumps(
                    slurmctld_info
                )
            else:
                relation.data[self.model.app]["slurmctld_info"] = ""

    def get_slurm_config_from_relation(self):
        """Return slurm_config."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                app_data = relation.data.get(app)
                if app_data:
                    if app_data.get("slurm_config"):
                        return json.loads(app_data["slurm_config"])
        return None

    def is_slurm_config_available(self):
        """Return True/False."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                app_data = relation.data.get(app)
                if app_data:
                    if app_data.get("slurm_config"):
                        return True
        return False
