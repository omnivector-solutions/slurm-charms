#!/usr/bin/env python3
"""Interface slurmd."""
import copy
import json
import logging
from typing import List

from ops.framework import (
    EventBase, EventSource, Object, ObjectEvents, StoredState
)


logger = logging.getLogger()


class SlurmdAvailableEvent(EventBase):
    """Emmited when slurmd is available."""


class SlurmdBrokenEvent(EventBase):
    """Emmited when the slurmd relation is broken."""


class SlurmdDepartedEvent(EventBase):
    """Emmited when one slurmd departs."""


class SlurmdInventoryEvents(ObjectEvents):
    """SlurmClusterProviderRelationEvents."""

    slurmd_available = EventSource(SlurmdAvailableEvent)
    slurmd_unavailable = EventSource(SlurmdBrokenEvent)
    slurmd_departed = EventSource(SlurmdDepartedEvent)


class Slurmd(Object):
    """Slurmd inventory interface."""

    on = SlurmdInventoryEvents()
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
            self._charm.on[self._relation_name].relation_departed,
            self._on_relation_departed,
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken,
        )

    def _on_relation_created(self, event):
        """Set our data on the relation."""
        # Check that slurm has been installed so that we know the munge key is
        # available. Defer if slurm has not been installed yet.
        if not self._charm.is_slurm_installed():
            event.defer()
            return

        # Get the munge_key from set it to the app data on the relation to be
        # retrieved on the other side by slurmdbd.
        app_relation_data = event.relation.data[self.model.app]
        app_relation_data["munge_key"] = self._charm.get_munge_key()

        # send the hostname and port to enable configless mode
        app_relation_data["slurmctld_host"] = self._charm.hostname
        app_relation_data["slurmctld_port"] = self._charm.port

    def set_list_of_accounted_nodes(self, nodes: List[str]):
        """Set list of accounted for nodes in the app relation data."""
        for relation in self._charm.framework.model.relations["slurmd"]:
            relation.data[self.model.app]["unit_hostnames"] = json.dumps(nodes)

    def _on_relation_changed(self, event):
        """Emit slurmd available event."""
        if event.relation.data[event.app].get("partition_info"):
            self._charm.set_slurmd_available(True)
            self.on.slurmd_available.emit()
        else:
            event.defer()

    def _on_relation_departed(self, event):
        """Handle hook when 1 unit departs."""
        self.on.slurmd_departed.emit()

    def _on_relation_broken(self, event):
        """Clear the munge key and emit the event if the relation is broken."""
        if self.framework.model.unit.is_leader():
            event.relation.data[self.model.app]["munge_key"] = ""

        # if there are other partitions, slurmctld needs to update the config
        # only. If there are no other partitions, we set slurmd_available to
        # False as well
        if self._num_relations:
            self.on.slurmd_available.emit()
        else:
            self._charm.set_slurmd_available(False)
            self.on.slurmd_unavailable.emit()

    @property
    def _num_relations(self):
        """Return the number of relations (number of slurmd applications)."""
        return len(self._charm.framework.model.relations[self._relation_name])

    @property
    def is_joined(self):
        """Return True if self._relation is not None."""
        if self._charm.framework.model.relations.get(self._relation_name):
            return True
        else:
            return False

    def get_slurmd_info(self) -> list:
        """Return the node info for units of applications on the relation."""
        partitions = list()
        relations = self.framework.model.relations["slurmd"]

        for relation in relations:
            inventory = list()

            app = relation.app
            units = relation.units
            # check if this partition has at least one node before adding it to
            # the list
            if units:
                if not relation.data.get(app):
                    logger.debug(f"## Not app data in relation with {app}")
                    return []
                if not relation.data[app].get("partition_info"):
                    logger.debug("## Not partition info data in relation")
                    return []

                partition_info = json.loads(relation.data[app].get("partition_info"))

                for unit in units:
                    inv = relation.data[unit].get("inventory")
                    if inv:
                        inventory.append(json.loads(inv))

                partition_info["inventory"] = inventory.copy()
                partitions.append(partition_info)

        return ensure_unique_partitions(partitions)


def ensure_unique_partitions(partitions):
    """Return a list of unique partitions."""
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
