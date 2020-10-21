#!/usr/bin/python3
"""SlurmctldPeer."""
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


class SlurmctldPeerAvailableEvent(EventBase):
    """Emmited on the relation_changed event."""


class SlurmctldPeerRelationEvents(ObjectEvents):
    """Slurmctld peer relation events."""

    slurmctld_peer_available = EventSource(SlurmctldPeerAvailableEvent)


class SlurmctldPeer(Object):
    """SlurmctldPeer Interface."""

    on = SlurmctldPeerRelationEvents()

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
        # emit the slurmctld_peer_available event.
        self._on_relation_changed(event)

    def _on_relation_changed(self, event):
        """Use the leader and app relation data to schedule the controllers."""
        # We only modify the slurmctld controller queue
        # if we are the leaader. As such, we dont need to preform
        # any operations if we are not the leader.
        if self.framework.model.unit.is_leader():
            relation = self.framework.model.get_relation(self._relation_name)

            app_relation_data = relation.data[self.model.app]
            unit_relation_data = relation.data[self.model.unit]

            slurmctld_peers = _get_active_peers()
            slurmctld_peers_tmp = copy.deepcopy(slurmctld_peers)

            active_controller = app_relation_data.get('active_controller')
            backup_controller = app_relation_data.get('backup_controller')

            # Account for the active controller
            # In this case, tightly couple the active controller to the leader.
            #
            # If we are the leader but are not the active controller,
            # then the previous leader or active controller must have died.
            if active_controller != self.model.unit.name:
                app_relation_data['active_controller'] = self.model.unit.name

            # Account for the backup and standby controllers
            #
            # If the backup controller exists in the application relation data
            # then check that it also exists in the slurmctld_peers. If it does
            # exist in the slurmctld peers then remove it from the list of
            # active peers and set the rest of the peers to be standby
            # controllers.
            if backup_controller:
                # Just because the backup_controller exists in the application
                # data doesn't mean that it really exists. Check that the
                # backup_controller that we have in the application data still
                # exists in the list of active units. If the backup_controller
                # isn't in the list of active units then check for
                # slurmctld_peers > 0 and try to promote a standby to a backup.
                if backup_controller in slurmctld_peers:
                    slurmctld_peers_tmp.remove(backup_controller)
                    app_relation_data['standby_controllers'] = json.dumps(
                        slurmctld_peers_tmp
                    )
                else:
                    if len(slurmctld_peers) > 0:
                        app_relation_data['backup_controller'] = \
                            slurmctld_peers_tmp.pop()
                        app_relation_data['standby_controllers'] = json.dumps(
                            slurmctld_peers_tmp
                        )
                    else:
                        app_relation_data['backup_controller'] = ""
                        app_relation_data['standby_controllers'] = json.dumps(
                            []
                        )
            else:
                if len(slurmctld_peers) > 0:
                    app_relation_data['backup_controller'] = \
                        slurmctld_peers_tmp.pop()
                    app_relation_data['standby_controllers'] = json.dumps(
                        slurmctld_peers_tmp
                    )
                else:
                    app_relation_data['standby_controllers'] = json.dumps([])

            ctxt = {}
            backup_controller = app_relation_data.get('backup_controller')

            # NOTE: We only care about the active and backup controllers.
            # Set the active controller info and check for and set the
            # backup controller information if one exists.
            ctxt['active_controller_ingress_address'] = \
                unit_relation_data['ingress-address']
            ctxt['active_controller_hostname'] = self._charm.get_hostname()
            ctxt['active_controller_port'] = str(self._charm.get_port())

            # If we have > 0 controllers (also have a backup), iterate over
            # them retrieving the info for the backup and set it along with
            # the info for the active controller, then emit the
            # 'slurmctld_peer_available' event.
            if backup_controller:
                for unit in relation.units:
                    if unit.name == backup_controller:
                        unit_data = relation.data[unit]
                        ctxt['backup_controller_ingress_address'] = \
                            unit_data['ingress-address']
                        ctxt['backup_controller_hostname'] = \
                            unit_data['hostname']
                        ctxt['backup_controller_port'] = unit_data['port']
            else:
                ctxt['backup_controller_ingress_address'] = ""
                ctxt['backup_controller_hostname'] = ""
                ctxt['backup_controller_port'] = ""

            app_relation_data['slurmctld_info'] = json.dumps(ctxt)
            self.on.slurmctld_peer_available.emit()

    def _on_relation_departed(self, event):
        self.on.slurmctld_peer_available.emit()

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    def get_slurmctld_info(self):
        """Return slurmctld info."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                app_data = relation.data.get(app)
                if app_data:
                    slurmctld_info = app_data.get('slurmctld_info')
                    if slurmctld_info:
                        return json.loads(slurmctld_info)
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
    for rel_id in _relation_ids('slurmctld-peer'):
        for unit in _related_units(rel_id):
            active_units.append(unit)
    return active_units
