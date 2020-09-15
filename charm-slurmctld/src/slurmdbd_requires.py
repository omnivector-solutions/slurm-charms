#!/usr/bin/python3
"""SlurmdbdRequiresRelation."""
import logging


from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
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

    def __init__(self, charm, relation_name):
        """Set the initial attribute values for this interface."""
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

        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_created(self, event):
        # Check that slurm has been installed so that we know the munge key is
        # available. Defer if slurm has not been installed yet.
        if not self._charm.is_slurm_installed():
            event.defer()
            return
        # Get the munge_key from the slurm_ops_manager and set it to the app
        # data on the relation to be retrieved on the other side by slurmdbd.
        munge_key = self._charm.get_munge_key()
        event.relation.data[self.model.app]['munge_key'] = munge_key

    def _on_relation_changed(self, event):
        # Retrieve the hostname, port and ingress-address from the event,
        # add them to the interface _state object.
        # Set slurmdbd_acquired = True and emit slurmdbd_available to be
        # observed by the main charm.
<<<<<<< HEAD
        event_unit_data = event.relation.data[event.unit]
        if event_unit_data.get('slurmdbd_available'):
            if event_unit_data['slurmdbd_available'] == "true":
                self._charm.set_slurmdbd_info({
                    'ingress_address': event_unit_data['ingress-address'],
                    'hostname': event_unit_data['hostname'],
                    'port': event_unit_data['port'],
                })
                self._charm.set_slurmdbd_available(True)
                self.on.slurmdbd_available.emit()
                return
        event.defer()
=======
        event_unit_data = event.relation.data.get(event.unit)
        if event_unit_data.get('slurmdbd_available', None) == "true":
            self._charm.set_slurmdbd_info({
                'ingress_address': event_unit_data['ingress-address'],
                'hostname': event_unit_data['hostname'],
                'port': event_unit_data['port'],
            })
            self.on.slurmdbd_available.emit()
        else:
            event.defer()
            return
>>>>>>> 5b6be961010cb4d984b7064ccacc4ec910b8e9c9

    def _on_relation_broken(self, event):
        self.on.slurmdbd_unavailable.emit()
