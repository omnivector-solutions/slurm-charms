#! /usr/bin/env python3
"""SlurmdbdRequiresRelation."""
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


class SlurmdbdAvailableEvent(EventBase):
    """Emits slurmdbd_available."""


class SlurmdbdUnAvailableEvent(EventBase):
    """Emits slurmdbd_unavailable."""


class SlurmdbdAvailableEvents(ObjectEvents):
    """SlurmdbdAvailableEvents."""

    slurmdbd_available = EventSource(SlurmdbdAvailableEvent)
    slurmdbd_unavailable = EventSource(SlurmdbdUnAvailableEvent)


class SlurmdbdRequiresRelation(Object):
    """SlurmdbdRequiresRelation."""

    on = SlurmdbdAvailableEvents()

    _state = StoredState()

    def __init__(self, charm, relation_name):
        """Set the initial attribute values for this interface."""
        super().__init__(charm, relation_name)

        self.charm = charm
        self._relation_name = relation_name

        self._state.set_default(slurmdbd_acquired=False)
        self._state.set_default(slurmdbd_info=dict())

        self.framework.observe(
            charm.on[self._relation_name].relation_created,
            self._on_relation_created
        )

        self.framework.observe(
            charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

        self.framework.observe(
            charm.on[self._relation_name].relation_broken,
            self._on_relation_broken
        )

    def get_slurmdbd_info(self):
        """Return the slurmdbd_info from the underlying _state object."""
        return self._state.slurmdbd_info

    @property
    def slurmdbd_acquired(self):
        """Return the boolean from the underlying _state object."""
        return self._state.slurmdbd_acquired

    def _on_relation_created(self, event):
        # Check that slurm has been installed so that we know the munge key is
        # available. Defer if slurm has not been installed yet.
        if not self.charm.slurm_ops_manager.slurm_installed:
            event.defer()
            return
        # Get the munge_key from the slurm_ops_manager and set it to the app
        # data on the relation to be retrieved on the other side by slurmdbd.
        munge_key = self.charm.slurm_ops_manager.get_munge_key()
        event.relation.data[self.model.app]['munge_key'] = munge_key

    def _on_relation_changed(self, event):
        # Retrieve the hostname, port and ingress-address from the event,
        # add them to the interface _state object.
        # Set slurmdbd_acquired = True and emit slurmdbd_available to be
        # observed by the main charm.
        event_unit_data = event.relation.data[event.unit]
        self._state.slurmdbd_info = json.dumps({
            'ingress_address': event_unit_data['ingress-address'],
            'hostname': event_unit_data['hostname'],
            'port': event_unit_data['port'],
        })
        if event_unit_data['slurmdbd_available'] == "true":
            self._state.slurmdbd_acquired = True
            self.on.slurmdbd_available.emit()
        else:
            event.defer()

    def _on_relation_broken(self, event):
        self._state.slurmdbd_acquired = False
        self.on.slurmdbd_unavailable.emit()
