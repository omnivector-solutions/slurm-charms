#!/usr/bin/python3
"""Slurm License interface."""
import json
import logging

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
    StoredState,
)


logger = logging.getLogger()


class SlurmLicenseAvailableEvent(EventBase):
    """Emmited when slurmlicense is available."""

class SlurmLicenseUnavailableEvent(EventBase):
    """Emmited when slurmlicense is available."""

class SlurmLicenseEvents(ObjectEvents):
    """SlurmlicenseEvents."""

    prolog_epilog_available = EventSource(SlurmLicenseAvailableEvent)
    prolog_epilog_unavailable = EventSource(SlurmLicenseUnavailableEvent)


class PrologEpilog(Object):
    """Epilog/prolog interface."""

    _stored = StoredState()
    on = SlurmLicenseEvents()

    def __init__(self, charm, relation_name):
        """Set the initial data."""
        super().__init__(charm, relation_name)

        self.charm = charm
        self._stored.set_default(
            prolog_epilog=dict(),
        )
        self.framework.observe(
            charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            charm.on[relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_changed(self, event):
        prolog = event.relation.data[event.unit].get('prolog', None)
        epilog = event.relation.data[event.unit].get('epilog', None)
        
        if not prolog:
            event.defer()
            return

        if not epilog:
            event.defer()
            return

        self._stored.prolog_epilog = json.dumps({
            'slurmctld_epilog_path': epilog,
            'slurmctld_prolog_path': prolog
        })

        # Store the license path in the charm's state
        self.charm.set_prolog_path(prolog)
        self.charm.set_epilog_path(epilog)

        self.charm.set_slurm_license_available(True)
        self.on.prolog_epilog_available.emit()

    def _on_relation_broken(self, event):
        self.charm.set_slurm_license_available(False)
    
    def get_prolog_epilog(self):
        info = self._stored.prolog_epilog
        if info:
            return json.loads(info)
        else:
            return None
