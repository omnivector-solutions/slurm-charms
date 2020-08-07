#!/usr/bin/python3
"""SlurmLoginProvides."""
import json
import logging


from ops.framework import Object


logger = logging.getLogger()


class SlurmLoginProvides(Object):
    """Login Provides Relation."""

    def __init__(self, charm, relation_name):
        """Set the provides initial data."""
        super().__init__(charm, relation_name)
        self.charm = charm
        self.framework.observe(
            charm.on[relation_name].relation_created,
            self._on_relation_created
        )

    def _on_relation_created(self, event):
        self.charm.set_slurm_login_available(True)
