#!/usr/bin/env python3
"""SlurmdPeer."""
from ops.framework import Object


class SlurmdPeer(Object):
    """SlurmdPeerRelation."""

    def __init__(self, charm, relation_name):
        """Initialize relation attributes."""
        super().__init__(charm, relation_name)
        self._relation_name = relation_name

    @property
    def _relation(self):
        """Return the Relation object for this relation."""
        return self.framework.model.get_relation(self._relation_name)

    @property
    def partition_name(self) -> str:
        """Return the partition name from the application data."""
        if self._relation:
            if self._relation.data.get(self.model.app):
                return self._relation.data[self.model.app].get("partition_name")
        return ""

    @partition_name.setter
    def partition_name(self, partition_name: str):
        """Set the partition name on the application data."""
        self._relation.data[self.model.app]["partition_name"] = partition_name

    @property
    def available(self) -> bool:
        """Return True if we have a relation, else False."""
        if not self._relation:
            return False
        return True
