#!/usr/bin/python3
"""SlurmdPeer."""
import json
import logging

from ops.framework import EventBase, EventSource, Object, ObjectEvents

from utils import get_active_units, get_inventory

logger = logging.getLogger(__name__)


class SlurmdPeerAvailableEvent(EventBase):
    """Emit this when slurmd peers join the relation."""


class SlurmdPeerDepartedEvent(EventBase):
    """Emit this when a peer departs."""


class PeerRelationEvents(ObjectEvents):
    """Peer Relation Events."""

    slurmd_peer_available = EventSource(SlurmdPeerAvailableEvent)
    slurmd_peer_departed = EventSource(SlurmdPeerDepartedEvent)


class SlurmdPeer(Object):
    """TestingPeerRelation."""

    on = PeerRelationEvents()

    def __init__(self, charm, relation_name):
        """Initialize charm attributes."""
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

    def _on_relation_created(self, event):
        node_name = self._charm.get_hostname()
        node_addr = event.relation.data[self.model.unit]["ingress-address"]

        inv = get_inventory(node_name, node_addr)
        inv["new_node"] = self._charm._stored.new_node
        event.relation.data[self.model.unit]["inventory"] = json.dumps(inv)

        if self.framework.model.unit.is_leader():
            self.on.slurmd_peer_available.emit()

    def _on_relation_changed(self, event):
        if self.framework.model.unit.is_leader():
            self.on.slurmd_peer_available.emit()

    def _on_relation_departed(self, event):
        if self.framework.model.unit.is_leader():
            self.on.slurmd_peer_departed.emit()

    def get_slurmd_inventory(self):
        """Return slurmd inventory."""
        relation = self.framework.model.get_relation(self._relation_name)

        # Comprise slurmd_info with the inventory of the active slurmd_peers
        # plus our own inventory.
        slurmd_peers = get_active_units(self._relation_name)
        peers = relation.units

        inventory = []

        for peer in peers:
            if peer.name in slurmd_peers:
                if relation.data.get(peer):
                    if relation.data[peer].get('inventory'):
                        inventory.append(json.loads(relation.data[peer]['inventory']))

        # Add our own inventory in with the other nodes
        inventory.append(
            json.loads(relation.data[self.model.unit]["inventory"])
        )
        return inventory
