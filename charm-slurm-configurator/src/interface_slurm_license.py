#!/usr/bin/python3
"""Slurm License interface."""
import json
import logging

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


logger = logging.getLogger()


class SlurmLicenseAvailableEvent(EventBase):
    """Emmited when slurmlicense is available."""

class SlurmLicenseUnavailableEvent(EventBase):
    """Emmited when slurmlicense is available."""

class SlurmLicenseEvents(ObjectEvents):
    """SlurmlicenseEvents."""

    slurm_license_available = EventSource(SlurmLicenseAvailableEvent)
    slurm_license_unavailable = EventSource(SlurmLicenseUnavailableEvent)


class SlurmLicense(Object):
    """SlurmLicense interface."""

    on = SlurmLicenseEvents()

    def __init__(self, charm, relation_name):
        """Set the initial data."""
        super().__init__(charm, relation_name)

        self.charm = charm
        self.framework.observe(
            charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            charm.on[relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_changed(self, event):
        logger.debug("################ inside relation changed 1 #######################")
        prolog = event.relation.data[event.unit].get('prolog', None)
        epilog = event.relation.data[event.unit].get('epilog', None)
        
        if not prolog:
            event.defer()
            return

        if not epilog:
            event.defer()
            return

        logger.debug("################ inside relation changed 2 #######################")
        logger.debug(epilog)
        logger.debug(prolog)

        # Store the license path in the charm's state
        self.charm.set_prolog_path(prolog)
        self.charm.set_epilog_path(epilog)

        self.charm.set_slurm_license_available(True)
        self.on.slurm_license_available.emit()

    def _on_relation_broken(self, event):
        self.charm.set_slurm_license_available(False)
        self.on.slurm_license_unavailable.emit()
