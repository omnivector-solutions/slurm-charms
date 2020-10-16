#!/usr/bin/python3
"""SlurmdPeer."""
import json
import logging


from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)
from utils import get_active_units, get_inventory


logger = logging.getLogger()


class SlurmdPeerAvailableEvent(EventBase):
    """Emmited on the relation_changed event."""


class PeerRelationEvents(ObjectEvents):
    """Peer Relation Events."""

    slurmd_peer_available = EventSource(SlurmdPeerAvailableEvent)


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
            self._on_relation_created
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

    def _on_relation_created(self, event):
        """Set our inventory on unit data."""
        node_name = self._charm.get_hostname()
        node_addr = event.relation.data[self.model.unit]['ingress-address']

        event.relation.data[self.model.unit]['inventory'] = json.dumps(
            get_inventory(node_name, node_addr)
        )
        if self.framework.model.unit.is_leader():
            self.on.slurmd_peer_available.emit()

    def _on_relation_changed(self, event):
        if self.framework.model.unit.is_leader():
            self.on.slurmd_peer_available.emit()

    def get_slurmd_info(self):
        """Return slurmd inventory."""
        relation = self.framework.model.get_relation(self._relation_name)

        # Comprise slurmd_info with the inventory of the active slurmd_peers
        # plus our own inventory.
        slurmd_peers = get_active_units(self._relation_name)
        peers = relation.units

        slurmd_info = [
            json.loads(relation.data[peer]['inventory'])
            for peer in peers if peer.name in slurmd_peers
        ]

        # Add our own inventory to the slurmd_info
        slurmd_info.append(
            json.loads(relation.data[self.model.unit]['inventory'])
        )

        return slurmd_info
