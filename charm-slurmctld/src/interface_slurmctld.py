#!/usr/bin/python3
"""Slurmctld."""
import json
import logging

from ops.framework import (
    EventBase, EventSource, Object, ObjectEvents, StoredState,
)


logger = logging.getLogger()


class MungeKeyAvailableEvent(EventBase):
    """Emitted when the munge key is acquired and saved."""


class RestartSlurmctldEvent(EventBase):
    """Emit this when slurmctld needs to be restarted."""


class ScontrolReconfigureEvent(EventBase):
    """Emit this when scontrol needs to be ran."""


class SlurmConfiguratorAvailableEvent(EventBase):
    """Emitted when slurm-config is available."""


class SlurmConfiguratorUnAvailableEvent(EventBase):
    """Emitted when a slurmctld unit joins the relation."""


class SlurmctldEvents(ObjectEvents):
    """Slurmctld emitted events."""

    slurm_config_available = EventSource(
        SlurmConfiguratorAvailableEvent
    )
    slurm_configurator_unavailable = EventSource(
        SlurmConfiguratorUnAvailableEvent
    )
    munge_key_available = EventSource(
        MungeKeyAvailableEvent
    )
    restart_slurmctld = EventSource(
        RestartSlurmctldEvent
    )
    scontrol_reconfigure = EventSource(
        ScontrolReconfigureEvent
    )


class Slurmctld(Object):
    """Slurmctld."""

    _stored = StoredState()
    on = SlurmctldEvents()

    def __init__(self, charm, relation_name):
        """Set initial data and observe interface events."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self._stored.set_default(
            slurm_config=dict(),
            munge_key=str(),
            restart_slurmctld_uuid=str(),
            scontrol_reconfigure_uuid=str(),
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
        self._store_munge_key(munge_key)
        self.on.munge_key_available.emit()

    def _on_relation_changed(self, event):
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            event.defer()
            return

        munge_key = event_app_data.get("munge_key")
        restart_slurmctld_uuid = event_app_data.get("restart_slurmctld_uuid")
        scontrol_reconfigure_uuid = event_app_data.get("scontrol_reconfigure_uuid")
        slurm_config = self._get_slurm_config_from_relation()

        if not (munge_key and slurm_config):
            event.defer()
            return

        # Store the munge_key in the interface StoredState if it has changed
        if munge_key != self.get_stored_munge_key():
            self._store_munge_key(munge_key)
            self.on.munge_key_available.emit()

        # Store the slurm_config in the interface StoredState if it has changed
        if slurm_config != self.get_stored_slurm_config():
            self._store_slurm_config(slurm_config)
            self.on.slurm_config_available.emit()

        if restart_slurmctld_uuid:
            if restart_slurmctld_uuid != self._get_restart_slurmctld_uuid():
                self._store_restart_slurmctld_uuid(restart_slurmctld_uuid)
                self.on.restart_slurmctld.emit()

        if scontrol_reconfigure_uuid:
            if scontrol_reconfigure_uuid != self._get_scontrol_reconfigure_uuid():
                self._store_scontrol_reconfigure_uuid(scontrol_reconfigure_uuid)
                self.on.scontrol_reconfigure.emit()

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

    def _get_slurm_config_from_relation(self):
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

    def _store_munge_key(self, munge_key):
        self._stored.munge_key = munge_key

    def get_stored_munge_key(self):
        """Retrieve the munge_key from stored state."""
        return self._stored.munge_key

    def _store_slurm_config(self, slurm_config):
        self._stored.slurm_config = slurm_config

    def get_stored_slurm_config(self):
        """Retrieve the slurm_config from stored state."""
        return self._stored.slurm_config

    def _store_restart_slurmctld_uuid(self, restart_slurmctld_uuid):
        self._stored.restart_slurmctld_uuid = restart_slurmctld_uuid

    def _store_scontrol_reconfigure_uuid(self, scontrol_reconfigure_uuid):
        self._stored.scontrol_reconfigure_uuid = scontrol_reconfigure_uuid

    def _get_restart_slurmctld_uuid(self):
        return self._stored.restart_slurmctld_uuid

    def _get_scontrol_reconfigure_uuid(self):
        return self._stored.restart_slurmctld_uuid
