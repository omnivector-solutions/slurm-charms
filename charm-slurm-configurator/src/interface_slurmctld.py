#!/usr/bin/python3
"""Slurmdbd."""
import json
import logging


from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


logger = logging.getLogger()


class SlurmctldAvailableEvent(EventBase):
    """Emits slurmctld_available."""


class SlurmctldUnAvailableEvent(EventBase):
    """Emits slurmctld_unavailable."""


class SlurmctldEvents(ObjectEvents):
    """SlurmctldEvents."""

    slurmctld_available = EventSource(SlurmctldAvailableEvent)
    slurmctld_unavailable = EventSource(SlurmctldUnAvailableEvent)


class Slurmctld(Object):
    """Facilitate slurmctld lifecycle events."""

    on = SlurmctldEvents()

    def __init__(self, charm, relation_name):
        """Observe the lifecycle events for this interface."""
        super().__init__(charm, relation_name)

        self._charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            self._charm.on[self._relation_name].relation_created,
            self._on_relation_created
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_departed,
            self._on_relation_departed
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
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
        app_relation_data['munge_key'] = self._charm.get_munge_key()

    def _on_relation_changed(self, event):
        event_app_data = event.relation.data.get(event.app)
        if event_app_data:
            slurmctld_info = event_app_data.get('slurmctld_info')
            if slurmctld_info:
                self._charm.set_slurmctld_available(True)
                self.on.slurmctld_available.emit()
        else:
            event.defer()
            return

    def _on_relation_departed(self, event):
        self.on.slurmctld_unavailable.emit()

    def _on_relation_broken(self, event):
        if self.framework.model.unit.is_leader():
            event.relation.data[self.model.app]['munge_key'] = ""
            self.set_slurm_config_on_app_relation_data("")
        self._charm.set_slurmctld_available(False)
        self.on.slurmctld_unavailable.emit()

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    def get_slurmctld_info(self):
        """Return the slurmctld_info."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                app_data = relation.data.get(app)
                if app_data:
                    slurmctld_info = app_data.get('slurmctld_info')
                    if slurmctld_info:
                        return json.loads(slurmctld_info)
        return None

    def set_slurm_config_on_app_relation_data(
        self,
        slurm_config,
    ):
        """Set the slurm_conifg to the app data on the relation.

        Setting data on the relation forces the units of related applications
        to observe the relation-changed event so they can acquire and
        render the updated slurm_config.
        """
        relations = self._charm.framework.model.relations['slurmctld']
        for relation in relations:
            app_relation_data = relation.data[self.model.app]
            if slurm_config != "":
                app_relation_data['slurm_config'] = json.dumps(slurm_config)
            else:
                app_relation_data['slurm_config'] = slurm_config
