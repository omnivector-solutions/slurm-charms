#!/usr/bin/python3
"""NhcRequires."""
from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


class NhcBinAvailableEvent(EventBase):
    """Emmited when the nhc_bin is received via relation data."""


class NhcEvents(ObjectEvents):
    """NhcEvents."""

    nhc_bin_available = EventSource(NhcBinAvailableEvent)


class NhcRequires(Object):
    """NhcRequires."""

    on = NhcEvents()

    def __init__(self, charm, relation_name):
        """Set self._relation_name and self.charm."""
        super().__init__(charm, relation_name)
        self.charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            self.charm.on[self._relation_name].relation_created,
            self._on_relation_created
        )
        self.framework.observe(
            self.charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

    def _on_relation_created(self, event):
        slurm_conf = "/var/snap/slurm/common/etc/slurm/slurm.conf"
        sinfo = "/snap/bin/slurm.sinfo"
        scontrol = "/snap/bin/slurm.scontrol"

        if self.framework.model.unit.is_leader():
            event_app_data = event.relation.data[self.model.app]
            event_app_data['slurm_conf'] = slurm_conf
            event_app_data['sinfo'] = sinfo
            event_app_data['scontrol'] = scontrol

    def _on_relation_changed(self, event):
        nhc_bin_path = event.relation.data[event.app]['nhc_bin']
        self._charm.set_nhc_bin_path(nhc_bin_path)
        self.on.nhc_bin_available.emit()
