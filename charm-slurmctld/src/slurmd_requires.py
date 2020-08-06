"""requires interface for slurmctld."""
import collections
import json
import logging
import socket
from pathlib import Path


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

        self._MUNGE_KEY_PATH = \
            Path("/var/snap/slurm/common/etc/munge/munge.key")

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
        self._state.ingress_address = unit_data['ingress-address']

    def _on_relation_changed(self, event):
        """Check for slurmdbd and slurmd, write config, set relation data."""
        if len(self.framework.model.relations['slurmd']) > 0:
            if not self.charm.is_slurmd_available():
                self.charm.set_slurmd_available(True)
            self.on.slurmd_available.emit()
        else:
            self.charm.unit.status = BlockedStatus("Need > 0 units of slurmd")
            event.defer()
            return

    def _on_relation_broken(self, event):
        """Account for relation broken activity."""
        if len(self.framework.model.relations['slurmd']) < 1:
            self.charm.set_slurmd_available(False)
            self.on.slurmd_unavailable.emit()

    @property
    def _partitions(self):
        """Parse the node_data and return the hosts -> partition mapping."""
        part_dict = collections.defaultdict(dict)
        for node in self._slurmd_node_data:
            part_dict[node['partition_name']].setdefault('hosts', [])
            part_dict[node['partition_name']]['hosts'].append(node['hostname'])
            part_dict[node['partition_name']]['partition_default'] = \
                node['partition_default']
            if node.get('partition_config'):
                part_dict[node['partition_name']]['partition_config'] = \
                    node['partition_config']
        return dict(part_dict)

    @property
    def _slurmd_node_data(self):
        """Return the node info for units of applications on the relation."""
        relations = self.framework.model.relations['slurmd']
        nodes_info = list()
        for relation in relations:
            for unit in relation.units:
                ctxt = {
                    'ingress_address': relation.data[unit]['ingress-address'],
                    'hostname': relation.data[unit]['hostname'],
                    'inventory': relation.data[unit]['inventory'],
                    'partition_name': relation.data[unit]['partition_name'],
                    'partition_default':
                    relation.data[unit]['partition_default'],
                }
                # Related slurmd units don't specify custom partition_config
                # by default. Only get partition_config if it exists on in the
                # related unit's unit data.
                if relation.data[unit].get('partition_config'):
                    ctxt['partition_config'] = \
                        relation.data[unit]['partition_config']
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
        relations = self.charm.framework.model.relations[relation]
        for relation in relations:
            relation.data[self.model.app]['slurm_config'] = json.dumps(
                slurm_config
            )

    def get_slurm_config(self):
        """Assemble and return the slurm_config."""
        slurmctld_ingress_address = self._state.ingress_address
        slurmctld_hostname = socket.gethostname().split(".")[0]

        slurmdbd_info = dict(self.charm.get_slurmdbd_info())

        return {
            'nodes': self._slurmd_node_data,
            'partitions': self._partitions,
            'slurmdbd_port': slurmdbd_info['port'],
            'slurmdbd_hostname': slurmdbd_info['hostname'],
            'slurmdbd_ingress_address': slurmdbd_info['ingress_address'],
            'active_controller_hostname': slurmctld_hostname,
            'active_controller_ingress_address': slurmctld_ingress_address,
            'active_controller_port': "6817",
            'munge_key': self.charm.get_munge_key(),
            **self.model.config,
        }
