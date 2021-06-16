#!/usr/bin/env python3
"""Slurmd."""
import json
import logging

from ops.framework import (
    EventBase, EventSource, Object, ObjectEvents, StoredState,
)

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
        """Handle the relation-created event.

        Set the node inventory and partition_name on the relation data.
        """
        # Generate the inventory and set it on the relation data.
        node_name = self._charm.hostname
        node_addr = event.relation.data[self.model.unit]["ingress-address"]

        inv = get_inventory(node_name, node_addr)
        inv["new_node"] = True
        self.node_inventory = inv

        if self.framework.model.unit.is_leader():
            # Set the partition name on the application data.
            partition_name = self._charm.get_partition_name()
            if not partition_name:
                event.defer()
                return

            event.relation.data[self.model.app]["partition_name"] = \
                partition_name

    def _on_relation_joined(self, event):
        """Handle the relation-joined event.

        Get the munge_key from slurmctld and save it to the charm stored state.
        """
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            event.defer()
            return

        # slurmctld sets the munge_key on the relation-created event
        # which happens before relation-joined. We can almost guarantee that
        # the munge key will exist at this point, but check for it just incase.
        munge_key = event_app_data.get("munge_key")
        if not munge_key:
            event.defer()
            return

        # Store the munge_key in the charm's state
        self._store_munge_key(munge_key)

        # get slurmctld's hostname and port to enable configless
        host = event_app_data.get("slurmctld_host")
        port = event_app_data.get("slurmctld_port")
        if not (host or port):
            event.defer()
        self._store_slurmctld_host_port(host, port)

        self._charm.set_slurmctld_available(True)
        self.on.slurmctld_available.emit()

    def _on_relation_broken(self, event):
        self._charm.set_slurmctld_available(False)
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

    @property
    def slurmctld_hostname(self):
        """Get slurmctld hostname."""
        return self._stored.slurmctld_hostname

    @property
    def slurmctld_port(self):
        """Get slurmctld port."""
        return self._stored.slurmctld_port

    @property
    def node_inventory(self):
        """Return unit inventory."""
        return json.loads(self._relation.data[self.model.unit].get("inventory"))

    @node_inventory.setter
    def node_inventory(self, inventory: dict):
        """Set unit inventory."""
        self._relation.data[self.model.unit]["inventory"] = \
            json.dumps(inventory)

    @property
    def partition_name(self):
        """Get partition name."""
        return self._relation.data[self.model.app].get('partition-name')

    @partition_name.setter
    def partition_name(self, name: str):
        """Set the partition name."""
        self._relation.data[self.model.app]['partition-name'] = name

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

    def _store_munge_key(self, munge_key):
        """Store the munge_key in the StoredState."""
        self._stored.munge_key = munge_key

    def _store_slurmctld_host_port(self, host, port):
        """Store the hostname and port of slurmctld in StoredState."""
        if host != self._stored.slurmctld_hostname:
            self._stored.slurmctld_hostname = host

        if port != self._stored.slurmctld_port:
            self._stored.slurmctld_port = port

    def _store_slurmd_restart_uuid(self, restart_slurmd_uuid):
        self._stored.restart_slurmd_uuid = restart_slurmd_uuid

    def _get_slurmd_restart_uuid(self):
        return self._stored.restart_slurmd_uuid

    def get_stored_munge_key(self):
        """Retrieve the munge_key from the StoredState."""
        return self._stored.munge_key

    def get_node_inventory(self):
        """Retrieve the node inventory from the relation."""
        return self._relation.data[self.model.unit].get("inventory")

    def configure_new_node(self):
        """Set this node as not new and trigger a reconfiguration."""
        inv = self._relation.data[self.model.unit].get("inventory")
        inv = json.loads(inv)
        inv["new_node"] = False

        self._relation.data[self.model.unit]['inventory'] = json.dumps(
            inv
        )

        self._charm._check_slurmd()
