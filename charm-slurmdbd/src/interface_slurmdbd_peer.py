#!/usr/bin/python3
"""SlurmdbdPeer."""
import copy
import json
import logging
import subprocess

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


logger = logging.getLogger()


class SlurmdbdPeerAvailableEvent(EventBase):
    """Emmited in the relation_changed event when a peer comes online."""


class SlurmdbdPeerRelationEvents(ObjectEvents):
    """Slurmdbd peer relation events."""

    slurmdbd_peer_available = EventSource(SlurmdbdPeerAvailableEvent)


class SlurmdbdPeer(Object):
    """SlurmdbdPeer Interface."""

    on = SlurmdbdPeerRelationEvents()

    def __init__(self, charm, relation_name):
        """Initialize and observe."""
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
            self._charm.on[self._relation_name].relation_departed,
            self._on_relation_departed
        )

    def _on_relation_created(self, event):
        """Set hostname and port on the unit data."""
        relation = self.framework.model.get_relation(self._relation_name)
        unit_relation_data = relation.data[self.model.unit]

        unit_relation_data['hostname'] = self._charm.get_hostname()
        unit_relation_data['port'] = self._charm.get_port()

        # Call _on_relation_changed to assemble the slurmctld_info and
        # emit the slurmdbd_peer_available event.
        self._on_relation_changed(event)

    def _on_relation_changed(self, event):
        """Use the leader and app relation data to schedule active/backup."""
        # We only modify the slurmdbd queue if we are the leaader.
        # As such, we dont need to preform any operations here
        # if we are not the leader.
        if self.framework.model.unit.is_leader():
            relation = self.framework.model.get_relation(self._relation_name)

            app_relation_data = relation.data[self.model.app]
            unit_relation_data = relation.data[self.model.unit]

            slurmdbd_peers = _get_active_peers()
            slurmdbd_peers_tmp = copy.deepcopy(slurmdbd_peers)

            active_slurmdbd = app_relation_data.get('active_slurmdbd')
            backup_slurmdbd = app_relation_data.get('backup_slurmdbd')

            # Account for the active slurmdbd
            # In this case, tightly couple the active slurmdbd to the leader.
            #
            # If we are the leader but are not the active slurmdbd,
            # then the previous slurmdbd leader must have died.
            # Set our unit to the active_slurmdbd.
            if active_slurmdbd != self.model.unit.name:
                app_relation_data['active_slurmdbd'] = self.model.unit.name

            # Account for the backup and standby slurmdbd
            #
            # If the backup slurmdbd exists in the application relation data
            # then check that it also exists in the slurmdbd_peers. If it does
            # exist in the slurmdbd peers then remove it from the list of
            # active peers and set the rest of the peers to be standbys.
            if backup_slurmdbd:
                # Just because the backup_slurmdbd exists in the application
                # data doesn't mean that it really exists. Check that the
                # backup_slurmdbd that we have in the application data still
                # exists in the list of active units. If the backup_slurmdbd
                # isn't in the list of active units then check for
                # slurmdbd_peers > 0 and try to promote a standby to a backup.
                if backup_slurmdbd in slurmdbd_peers:
                    slurmdbd_peers_tmp.remove(backup_slurmdbd)
                    app_relation_data['standby_slurmdbd'] = json.dumps(
                        slurmdbd_peers_tmp
                    )
                else:
                    if len(slurmdbd_peers) > 0:
                        app_relation_data['backup_slurmdbd'] = \
                            slurmdbd_peers_tmp.pop()
                        app_relation_data['standby_slurmdbd'] = json.dumps(
                            slurmdbd_peers_tmp
                        )
                    else:
                        app_relation_data['backup_slurmdbd'] = ""
                        app_relation_data['standby_slurmdbd'] = json.dumps(
                            []
                        )
            else:
                if len(slurmdbd_peers) > 0:
                    app_relation_data['backup_slurmdbd'] = \
                        slurmdbd_peers_tmp.pop()
                    app_relation_data['standby_slurmdbd'] = json.dumps(
                        slurmdbd_peers_tmp
                    )
                else:
                    app_relation_data['standby_slurmdbd'] = json.dumps([])

            ctxt = {}
            backup_slurmdbd = app_relation_data.get('backup_slurmdbd')

            # NOTE: We only care about the active and backup slurdbd.
            # Set the active slurmdbd info and check for and set the
            # backup slurmdbd information if one exists.
            ctxt['active_slurmdbd_ingress_address'] = \
                unit_relation_data['ingress-address']
            ctxt['active_slurmdbd_hostname'] = self._charm.get_hostname()
            ctxt['active_slurmdbd_port'] = str(self._charm.get_port())

            # If we have > 0 slurmdbd (also have a backup), iterate over
            # them retrieving the info for the backup and set it along with
            # the info for the active slurmdbd, then emit the
            # 'slurmdbd_peer_available' event.
            if backup_slurmdbd:
                for unit in relation.units:
                    if unit.name == backup_slurmdbd:
                        unit_data = relation.data[unit]
                        ctxt['backup_slurmdbd_ingress_address'] = \
                            unit_data['ingress-address']
                        ctxt['backup_slurmdbd_hostname'] = \
                            unit_data['hostname']
                        ctxt['backup_slurmdbd_port'] = unit_data['port']
            else:
                ctxt['backup_slurmdbd_ingress_address'] = ""
                ctxt['backup_slurmdbd_hostname'] = ""
                ctxt['backup_slurmdbd_port'] = ""

            app_relation_data['slurmdbd_info'] = json.dumps(ctxt)
            self.on.slurmdbd_peer_available.emit()

    def _on_relation_departed(self, event):
        self.on.slurmdbd_peer_available.emit()

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    def get_slurmdbd_info(self):
        """Return slurmdbd info."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                slurmdbd_info = relation.data[app].get('slurmdbd_info')
                if slurmdbd_info:
                    return json.loads(slurmdbd_info)
        return None


def _related_units(relid):
    """List of related units."""
    units_cmd_line = ['relation-list', '--format=json', '-r', relid]
    return json.loads(
        subprocess.check_output(units_cmd_line).decode('UTF-8')) or []


def _relation_ids(reltype):
    """List of relation_ids."""
    relid_cmd_line = ['relation-ids', '--format=json', reltype]
    return json.loads(
        subprocess.check_output(relid_cmd_line).decode('UTF-8')) or []


def _get_active_peers():
    """Return the active_units."""
    active_units = []
    for rel_id in _relation_ids('slurmdbd-peer'):
        for unit in _related_units(rel_id):
            active_units.append(unit)
    return active_units
