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
        slurmdbd_acquired = self.charm.is_slurmdbd_available()
        slurmd_acquired = self.charm.is_slurmd_available()
        slurm_installed = self.charm.is_slurm_installed()
        if not (slurmdbd_acquired and slurmd_acquired and slurm_installed):
            event.defer()
            return
        else:
            # Send the current slurm_config, let the slurmd relation-changed
            # update the relation data for additional config changes.
            event.relation.data[self.model.app]["slurm_config"] = json.dumps(
                self.charm.get_slurm_config()
            )
            self.charm.set_slurm_login_available(True)
