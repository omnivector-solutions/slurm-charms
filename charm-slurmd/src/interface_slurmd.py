#!/usr/bin/env python3
"""Slurmd."""
import json
import logging

from ops.framework import (
    EventBase, EventSource, Object, ObjectEvents, StoredState,
)
from ops.model import Relation
from utils import get_inventory


logger = logging.getLogger(__name__)


class SlurmctldAvailableEvent(EventBase):
    """Emitted when slurmctld is available."""


class SlurmctldUnavailableEvent(EventBase):
    """Emit when the relation to slurmctld is broken."""


class SlurmdEvents(ObjectEvents):
    """Slurmd emitted events."""

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
            munge_key=str(),
            restart_slurmd_uuid=str(),
            slurmctld_hostname=str(),
            slurmctld_port=str(),
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
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken,
        )

    def _on_relation_created(self, event):
        """
        Handle the relation-created event.

        Set the node inventory on the relation data.
        """
        # Generate the inventory and set it on the relation data.
        node_name = self._charm.hostname
        node_addr = event.relation.data[self.model.unit]["ingress-address"]

        inv = get_inventory(node_name, node_addr)
        inv["new_node"] = True
        self.node_inventory = inv

    def _on_relation_joined(self, event):
        """
        Handle the relation-joined event.

        Get the munge_key, slurmctld_host and slurmctld_port from slurmctld
        and save it to the charm stored state.
        """
        app_data = event.relation.data[event.app]

        # slurmctld sets the munge_key on the relation-created event
        # which happens before relation-joined. We can guarantee that
        # the munge_key, slurmctld_host and slurmctld_port will exist
        # at this point so retrieve them from the relation data and store
        # them in the charm's stored state.
        self._store_munge_key(app_data["munge_key"])
        self._store_slurmctld_host_port(app_data["slurmctld_host"],
                                        app_data["slurmctld_port"])

        # Set slurmctld_available to true and emit the slurmctld_available event.
        self._charm.set_slurmctld_available(True)
        self.on.slurmctld_available.emit()

    def _on_relation_broken(self, event):
        """Perform relation broken operations."""
        self._charm.set_slurmctld_available(False)
        self.on.slurmctld_unavailable.emit()

    @property
    def _relation(self) -> Relation:
        """Return the relation."""
        return self.framework.model.get_relation(self._relation_name)

    @property
    def num_relations(self) -> int:
        """Return the number of relations."""
        return len(self._charm.framework.model.relations["slurmd"])

    @property
    def is_joined(self) -> bool:
        """Return True if relation is joined."""
        return self.num_relations > 0

    @property
    def slurmctld_hostname(self) -> str:
        """Get slurmctld hostname."""
        return self._stored.slurmctld_hostname

    @property
    def slurmctld_port(self) -> str:
        """Get slurmctld port."""
        return self._stored.slurmctld_port

    @property
    def node_inventory(self) -> dict:
        """Return unit inventory."""
        return json.loads(self._relation.data[self.model.unit]["inventory"])

    @node_inventory.setter
    def node_inventory(self, inventory: dict):
        """Set unit inventory."""
        self._relation.data[self.model.unit]["inventory"] = json.dumps(inventory)

    def set_partition_info_on_app_relation_data(self, partition_info):
        """Set the slurmd partition on the app relation data.

        Setting data on the application relation forces the units of related
        slurmctld application(s) to observe the relation-changed
        event so they can acquire and redistribute the updated slurm config.
        """
        # there is only one slurmctld, so there should be only one relation here
        relations = self._charm.framework.model.relations["slurmd"]
        for relation in relations:
            relation.data[self.model.app]["partition_info"] = json.dumps(
                partition_info
            )

    def _store_munge_key(self, munge_key: str):
        """Store the munge_key in the StoredState."""
        self._stored.munge_key = munge_key

    def _store_slurmctld_host_port(self, host: str, port: str):
        """Store the hostname and port of slurmctld in StoredState."""
        if host != self._stored.slurmctld_hostname:
            self._stored.slurmctld_hostname = host

        if port != self._stored.slurmctld_port:
            self._stored.slurmctld_port = port

    def _store_slurmd_restart_uuid(self, restart_slurmd_uuid: str):
        self._stored.restart_slurmd_uuid = restart_slurmd_uuid

    def _get_slurmd_restart_uuid(self) -> str:
        return self._stored.restart_slurmd_uuid

    def get_stored_munge_key(self) -> str:
        """Retrieve the munge_key from the StoredState."""
        return self._stored.munge_key

    def configure_new_node(self):
        """Set this node as not new and trigger a reconfiguration."""
        inv = self.node_inventory
        inv["new_node"] = False
        self.node_inventory = inv
        self._charm._check_slurmd()
