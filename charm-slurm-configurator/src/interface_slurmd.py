#!/usr/bin/python3
"""Slurmd."""
import json
import logging
import socket

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
    StoredState,
)
from utils import get_inventory

logger = logging.getLogger()


class SlurmdUnAvailableEvent(EventBase):
    """Emmited when the slurmd relation is broken."""


class SlurmdDepartedEvent(EventBase):
    """Emmited when a slurmd unit departs."""


class SlurmdAvailableEvent(EventBase):
    """Emmited when slurmd is available."""


class SlurmdRequiresEvents(ObjectEvents):
    """SlurmClusterProviderRelationEvents."""

    slurmd_available = EventSource(SlurmdAvailableEvent)
    slurmd_departed = EventSource(SlurmdDepartedEvent)
    slurmd_unavailable = EventSource(SlurmdUnAvailableEvent)


class Slurmd(Object):
    """Slurmd."""

    on = SlurmdRequiresEvents()
    _state = StoredState()

    def __init__(self, charm, relation_name):
        """Set self._relation_name and self.charm."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            self._charm.on[self._relation_name].relation_created,
            self._on_relation_created
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_joined,
            self._on_relation_joined
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
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

    def _on_relation_joined(self, event):
        partition_name = event.relation.data[event.app].get('partition_name')
        if not partition_name:
            event.defer()
            return

        if not self._charm.get_default_partition():
            self._charm.set_default_partition(partition_name)

    def _on_relation_changed(self, event):
        event_app_data = event.relation.data.get(event.app)
        if event_app_data:
            slurmd_info = event_app_data.get('slurmd_info')
            if slurmd_info:
                self._charm.set_slurmd_available(True)
                self.on.slurmd_available.emit()
        else:
            event.defer()
            return

    def _on_relation_broken(self, event):
        if self.framework.model.unit.is_leader():
            event.relation.data[self.model.app]['munge_key'] = ""
            self.set_slurm_config_on_app_relation_data("")
        self._charm.set_slurmd_available(False)

    def _assemble_slurm_configurator_inventory(self):
        """Assemble the slurm-configurator partition."""
        hostname = socket.gethostname()
        inventory = get_inventory(hostname, hostname)

        return {
            'inventory': [inventory],
            'partition_name': 'configurator',
            'partition_state': 'DRAIN',
            'partition_config': ''
        }

    def get_slurmd_info(self):
        """Return the node info for units of applications on the relation."""
        nodes_info = []
        relations = self.framework.model.relations['slurmd']

        for relation in relations:
            app = relation.app
            if app:
                app_data = relation.data.get(app)
                if app_data:
                    slurmd_info = app_data.get('slurmd_info')
                    if slurmd_info:
                        nodes_info.append(json.loads(slurmd_info))

        slurm_configurator = self._assemble_slurm_configurator_inventory()
        nodes_info.append(slurm_configurator)
        return nodes_info

    def set_slurm_config_on_app_relation_data(
        self,
        slurm_config,
    ):
        """Set the slurm_conifg to the app data on the relation.

        Setting data on the relation forces the units of related applications
        to observe the relation-changed event so they can acquire and
        render the updated slurm_config.
        """
        relations = self._charm.framework.model.relations['slurmd']
        for relation in relations:
            app_relation_data = relation.data[self.model.app]
            app_relation_data['slurm_config'] = json.dumps(slurm_config)
