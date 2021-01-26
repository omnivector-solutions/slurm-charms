#!/usr/bin/python3
"""Slurmd."""
import copy
import json
import logging
import socket

from ops.framework import EventBase, EventSource, Object, ObjectEvents, StoredState

from utils import get_inventory

logger = logging.getLogger()


class SlurmdAvailableEvent(EventBase):
    """Emmited when slurmd is available."""


class SlurmdBrokenEvent(EventBase):
    """Emmited when the slurmd relation is broken."""


class SlurmdDepartedEvent(EventBase):
    """Emmited when a slurmd unit departs."""


class SlurmdRequiresEvents(ObjectEvents):
    """SlurmClusterProviderRelationEvents."""

    slurmd_available = EventSource(SlurmdAvailableEvent)
    slurmd_departed = EventSource(SlurmdDepartedEvent)
    slurmd_unavailable = EventSource(SlurmdBrokenEvent)


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
            self._on_relation_created,
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
        # Check that slurm has been installed so that we know the munge key is
        # available. Defer if slurm has not been installed yet.
        if not self._charm.is_slurm_installed():
            event.defer()
            return
        # Get the munge_key from the slurm_ops_manager and set it to the app
        # data on the relation to be retrieved on the other side by slurmdbd.
        app_relation_data = event.relation.data[self.model.app]
        app_relation_data["munge_key"] = self._charm.get_munge_key()

    def _on_relation_changed(self, event):
        event_app_data = event.relation.data.get(event.app)
        if event_app_data:
            slurmd_info = event_app_data.get("slurmd_info")
            if slurmd_info:
                self._charm.set_slurmd_available(True)
                self.on.slurmd_available.emit()
        else:
            event.defer()
            return

    def _on_relation_broken(self, event):
        if self.framework.model.unit.is_leader():
            event.relation.data[self.model.app]["munge_key"] = ""
            self.set_slurm_config_on_app_relation_data("")
        self._charm.set_slurmd_available(False)
        self.on.slurmd_unavailable.emit()

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    @property
    def is_joined(self):
        """Return True if self._relation is not None."""
        return self._relation is not None

    def _assemble_slurm_configurator_inventory(self):
        """Assemble the slurm-configurator partition."""
        hostname = socket.gethostname()
        inventory = get_inventory(hostname, hostname)

        return {
            "inventory": [inventory],
            "partition_name": "configurator",
            "partition_state": "INACTIVE",
            "partition_config": "",
        }

    def get_slurmd_info(self):
        """Return the node info for units of applications on the relation."""
        partitions = []
        relations = self.framework.model.relations["slurmd"]

        for relation in relations:
            app = relation.app
            if app:
                app_data = relation.data.get(app)
                if app_data:
                    slurmd_info = app_data.get("slurmd_info")
                    if slurmd_info:
                        partitions.append(json.loads(slurmd_info))

        slurm_configurator = self._assemble_slurm_configurator_inventory()
        partitions.append(slurm_configurator)

        # Ensure we have partitions with unique inventory only
        #
        # 1) Create a temp copy of the partitions list and iterate
        # over it.
        #
        # 2) On each pass create a temp copy of the partition itself.
        #
        # 3) Get the inventory from the temp partition and iterate over it to
        # ensure we have unique entries.
        #
        # 4) Add the unique inventory back to the temp partition and
        # subsequently add the temp partition back to the original partitions
        # list.
        #
        # 5) Return the list of partitions with unique inventory.

        partitions_tmp = copy.deepcopy(partitions)
        for partition in partitions_tmp:

            partition_tmp = copy.deepcopy(partition)
            partitions.remove(partition)

            inventory = partition_tmp["inventory"]

            unique_inventory = list(
                {node["node_name"]: node for node in inventory}.values()
            )

            partition_tmp["inventory"] = unique_inventory
            partitions.append(partition_tmp)

        return partitions

    def set_slurm_config_on_app_relation_data(
        self,
        slurm_config,
    ):
        """Set the slurm_conifg to the app data on the relation.

        Setting data on the relation forces the units of related applications
        to observe the relation-changed event so they can acquire and
        render the updated slurm_config.
        """
        relations = self._charm.framework.model.relations["slurmd"]
        for relation in relations:
            app_relation_data = relation.data[self.model.app]
            app_relation_data["slurm_config"] = json.dumps(slurm_config)
