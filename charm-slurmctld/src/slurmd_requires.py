"""requires interface for slurmctld."""
import collections
import json
import logging

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


class SlurmdAvailableEvent(EventBase):
    """Emmited when slurmd is available."""


class SlurmdRequiresEvents(ObjectEvents):
    """SlurmClusterProviderRelationEvents."""

    slurmd_available = EventSource(SlurmdAvailableEvent)
    slurmd_unavailable = EventSource(SlurmdUnAvailableEvent)


class SlurmdRequires(Object):
    """SlurmdRequires."""

    on = SlurmdRequiresEvents()
    _state = StoredState()

    def __init__(self, charm, relation_name):
        """Set self._relation_name and self.charm."""
        super().__init__(charm, relation_name)
        self.charm = charm
        self._relation_name = relation_name

        self._state.set_default(slurmd_acquired=False)
        self._state.set_default(ingress_address=None)

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

    def _on_relation_created(self, event):
        unit_data = event.relation.data[self.model.unit]
        self._state.slurmd_acquired = True
        self._state.ingress_address = unit_data['ingress-address']

    def _on_relation_changed(self, event):
        slurmdbd_acquired = self.charm.slurmdbd.slurmdbd_acquired
        slurmctld_ingress_address = self._state.ingress_address

        if (slurmdbd_acquired and slurmctld_ingress_address):
            slurm_config = json.dumps(self.get_slurm_config())
            event.relation.data[self.model.app]['slurm_config'] = slurm_config
            self.on.slurmd_available.emit()
        else:
            self.charm.unit.status = BlockedStatus("Need relation to slurmdbd")
            event.defer()
            return

    def _on_relation_broken(self, event):
        """Account for relation broken activity."""
        if len(self.framework.model.relations['slurmd']) < 1:
            self._state.slurmd_acquired = False
            self.on.slurmd_unavailable.emit()

    @property
    def slurmd_acquired(self):
        """Return a bool from the underlying _state object."""
        return self._state.slurmd_acquired

    @property
    def _partitions(self):
        """Parse the node_data and return the hosts -> partition mapping."""
        part_dict = collections.defaultdict(dict)
        for node in self._slurmd_node_data:
            part_dict[node['partition']].setdefault('hosts', [])
            part_dict[node['partition']]['hosts'].append(node['hostname'])
            part_dict[node['partition']]['default'] = node['default']
        return dict(part_dict)

    @property
    def _slurmd_node_data(self):
        """Return the node info for units of applications on the relation."""
        relations = self.framework.model.relations['slurmd']
        nodes_info = list()
        for relation in relations:
            for unit in relation.units:
                nodes_info.append({
                    'ingress_address': relation.data[unit]['ingress-address'],
                    'hostname': relation.data[unit]['hostname'],
                    'partition': relation.data[unit]['partition'],
                    'inventory': relation.data[unit]['inventory'],
                    'default': relation.data[unit]['default'],
                })
        return nodes_info

    def set_slurm_config_on_app_relation_data(self):
        """Set the slurm_conifg to the app data on the relation.

        Setting data on the relation forces the units of related applications
        to observe the relation-changed event so they can acquire and
        render the updated slurm_config.
        """
        slurmd_relations = self.framework.model.relations['slurmd']
        slurm_config = json.dumps(self.get_slurm_config())
        # Iterate over each of the relations setting the slurm_config on each.
        for relation in slurmd_relations:
            relation.data[self.model.app]['slurm_config'] = slurm_config

    def get_slurm_config(self):
        """Assemble and return the slurm_config."""
        slurmdbd_acquired = self.charm.slurmdbd.slurmdbd_acquired
        slurmctld_ingress_address = self._state.ingress_address
        slurmctld_hostname = self.charm.slurm_ops_manager.hostname

        if not (slurmdbd_acquired and slurmctld_ingress_address):
            self.charm.unit.status = BlockedStatus(
                "Need relation to slurmdbd."
            )
            return {}

        slurmdbd_info = json.loads(
            self.charm.slurmdbd.get_slurmdbd_info()
        )

        return {
            'nodes': self._slurmd_node_data,
            'partitions': self._partitions,
            'slurmdbd_port': slurmdbd_info['port'],
            'slurmdbd_hostname': slurmdbd_info['hostname'],
            'slurmdbd_ingress_address': slurmdbd_info['ingress_address'],
            'active_controller_hostname': slurmctld_hostname,
            'active_controller_ingress_address': slurmctld_ingress_address,
            'active_controller_port': self.charm.slurm_ops_manager.port,
            'munge_key': self.charm.slurm_ops_manager.get_munge_key(),
            **self.model.config,
        }
