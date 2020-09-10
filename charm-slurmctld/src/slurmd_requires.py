#!/usr/bin/python3
"""SlurmdRequires."""
import collections
import json
import logging
import socket
import subprocess


from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
    StoredState,
)
from ops.model import BlockedStatus


logger = logging.getLogger()


class SlurmdUnAvailableEvent(EventBase):
    """Emmited when the slurmd relation is broken."""


class SlurmdDepartedEvent(EventBase):
    """Emmited when a slurmd unit departs."""


class SlurmdAvailableEvent(EventBase):
    """Emmited when slurmd is available."""


class SlurmdRequiresEvents(ObjectEvents):
    """SlurmClusterProviderRelationEvents."""

    slurmd_available = EventSource(SlurmdAvailableEvent)
    slurmd_departed = EventSource(SlurmdDepartedEvent)
    slurmd_unavailable = EventSource(SlurmdUnAvailableEvent)


class SlurmdRequires(Object):
    """SlurmdRequires."""

    on = SlurmdRequiresEvents()
    _state = StoredState()

    def __init__(self, charm, relation_name):
        """Set self._relation_name and self.charm."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self._state.set_default(ingress_address=None)

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
        self.framework.observe(
            self._charm.on[self._relation_name].relation_departed,
            self._on_relation_departed
        )

    def _on_relation_created(self, event):
        unit_data = event.relation.data[self.model.unit]
        self._state.ingress_address = unit_data['ingress-address']

    def _on_relation_changed(self, event):
        """Check for slurmdbd and slurmd, write config, set relation data."""
        if len(self.framework.model.relations['slurmd']) > 0:
            if not self._charm.is_slurmd_available():
                self._charm.set_slurmd_available(True)
            self.on.slurmd_available.emit()
        else:
            self._charm.unit.status = BlockedStatus("Need > 0 units of slurmd")
            event.defer()
            return

    def _on_relation_departed(self, event):
        """Account for relation departed activity."""
        relations = len(_get_slurmd_active_units())
        logger.debug(f"number of slurmd relations:  {relations}")
        if relations < 1:
            self._charm.set_slurmd_available(False)
        self.on.slurmd_departed.emit()

    def _on_relation_broken(self, event):
        """Account for relation broken activity."""
        pass

    def _get_partitions(self, node_data):
        """Parse the node_data and return the hosts -> partition mapping."""
        part_dict = collections.defaultdict(dict)
        for node in node_data:
            part_dict[node['partition_name']].setdefault('hosts', [])
            part_dict[node['partition_name']]['hosts'].append(node['hostname'])
            part_dict[node['partition_name']]['partition_default'] = \
                True if node['partition_default'] == "true" else False
            if node.get('partition_config'):
                part_dict[node['partition_name']]['partition_config'] = \
                    node['partition_config']
        return dict(part_dict)

    def _get_slurmd_node_data(self):
        """Return the node info for units of applications on the relation."""
        nodes_info = list()
        relations = self.framework.model.relations['slurmd']

        slurmd_active_units = _get_slurmd_active_units()

        for relation in relations:
            app = relation.app
            for unit in relation.units:
                if unit.name in slurmd_active_units:
                    unit_data = relation.data[unit]
                    app_data = relation.data[app]
                    ctxt = {
                        'ingress_address': unit_data['ingress-address'],
                        'hostname': unit_data['hostname'],
                        'inventory': unit_data['inventory'],
                        'partition_name': app_data['partition_name'],
                        'partition_default': app_data['partition_default'],
                    }
                    # Related slurmd units don't specify custom
                    # partition_config by default.
                    # Only get partition_config if it exists on in the
                    # related unit's unit data.
                    if app_data.get('partition_config'):
                        ctxt['partition_config'] = \
                                app_data['partition_config']
                    nodes_info.append(ctxt)
        return nodes_info

    def set_slurm_config_on_app_relation_data(
        self,
        relation,
        slurm_config,
    ):
        """Set the slurm_conifg to the app data on the relation.

        Setting data on the relation forces the units of related applications
        to observe the relation-changed event so they can acquire and
        render the updated slurm_config.
        """
        relations = self._charm.framework.model.relations[relation]
        for relation in relations:
            relation.data[self.model.app]['slurm_config'] = json.dumps(
                slurm_config
            )

    def get_slurm_config(self):
        """Assemble and return the slurm_config."""
        slurmctld_ingress_address = self._state.ingress_address
        slurmctld_hostname = socket.gethostname().split(".")[0]

        slurmdbd_info = dict(self._charm.get_slurmdbd_info())
        slurmd_node_data = self._get_slurmd_node_data()
        partitions = self._get_partitions(slurmd_node_data)

        if slurmd_node_data and partitions:
            return {
                'nodes': slurmd_node_data,
                'partitions': partitions,
                'slurmdbd_port': slurmdbd_info['port'],
                'slurmdbd_hostname': slurmdbd_info['hostname'],
                'slurmdbd_ingress_address': slurmdbd_info['ingress_address'],
                'active_controller_hostname': slurmctld_hostname,
                'active_controller_ingress_address': slurmctld_ingress_address,
                'active_controller_port': "6817",
                'munge_key': self._charm.get_munge_key(),
                **self.model.config,
            }
        else:
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


def _get_slurmd_active_units():
    """Return the active_units."""
    active_units = []
    for rel_id in _relation_ids('slurmd'):
        for unit in _related_units(rel_id):
            active_units.append(unit)
    return active_units
