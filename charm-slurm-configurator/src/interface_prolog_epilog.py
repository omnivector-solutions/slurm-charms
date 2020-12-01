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


class PrologEpilogAvailableEvent(EventBase):
    """Emmited when the prolog and epilog are available."""


class PrologEpilogUnavailableEvent(EventBase):
    """Emmited when the prolog and epilog are unavailable."""


class SlurmLicenseEvents(ObjectEvents):
    """SlurmlicenseEvents."""

    prolog_epilog_available = EventSource(PrologEpilogAvailableEvent)
    prolog_epilog_unavailable = EventSource(PrologEpilogUnavailableEvent)


class PrologEpilog(Object):
    """Epilog/prolog interface."""

    _stored = StoredState()
    on = SlurmLicenseEvents()

    def __init__(self, charm, relation_name):
        """Set the initial data."""
        super().__init__(charm, relation_name)

        self._charm = charm
        self._stored.set_default(
            prolog_epilog=str(),
        )
        self.framework.observe(
            self._charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            self._charm.on[relation_name].relation_broken,
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

        self.on.prolog_epilog_available.emit()

    def _on_relation_broken(self, event):
        self._stored.prolog_epilog = ""
        self.on.prolog_epilog_unavailable.emit()

    def get_prolog_epilog(self):
        """Get path of epilog/prolog."""
        info = self._stored.prolog_epilog
        if info:
            return json.loads(info)
        else:
            return None
