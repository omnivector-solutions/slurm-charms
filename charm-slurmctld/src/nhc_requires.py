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
        self._charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            self.on[self._relation_name].relation_created,
            self._on_relation_created
        )
        self.framework.observe(
            self.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

    def _on_relation_created(self, event):
        slurm_conf = "/var/snap/slurm/common/etc/slurm/slurm.conf"
        sinfo = "/snap/bin/slurm.sinfo"
        scontrol = "/snap/bin/slurm.scontrol"

        if self.framework.model.unit.is_leader():
            my_app_data = event.relation.data[self.model.app]
            my_app_data['slurm_conf'] = slurm_conf
            my_app_data['sinfo'] = sinfo
            my_app_data['scontrol'] = scontrol

    def _on_relation_changed(self, event):
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            event.defer()
            return

        nhc_bin_path = event_app_data.get('nhc_bin')
        nhc_health_check_interval = event_app_data.get('health_check_interval')
        nhc_health_check_node_state = event_app_data.get(
            'health_check_node_state'
        )
        if not (nhc_bin_path and nhc_health_check_interval and
                nhc_health_check_node_state):
            event.defer()
            return

        self._charm.set_nhc_info({
           'nhc_bin': nhc_bin_path,
           'health_check_interval': nhc_health_check_interval,
           'health_check_node_state': nhc_health_check_node_state,
        })
        self.on.nhc_bin_available.emit()
