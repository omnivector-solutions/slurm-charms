#!/usr/bin/env python3
"""Slurmctld."""
from ast import literal_eval
import json
import logging

from ops.framework import (
    EventBase, EventSource, Object, ObjectEvents, StoredState,
)


logger = logging.getLogger()


class MungeKeyAvailableEvent(EventBase):
    """Emitted when the munge key is acquired and saved."""


class RestartSlurmctldEvent(EventBase):
    """Emit this when slurmctld needs to be restarted."""


class ScontrolReconfigureEvent(EventBase):
    """Emit this when scontrol needs to be ran."""


class ScontrolUpdateEvent(EventBase):
    """Emit this when scontrol needs to be ran."""


class SlurmConfiguratorAvailableEvent(EventBase):
    """Emitted when slurm configurator relation has joined."""


class SlurmConfiguratorUnAvailableEvent(EventBase):
    """Emitted when a slurmctld unit joins the relation."""


class SlurmConfigAvailableEvent(EventBase):
    """Emitted when slurm-config is available."""


class SlurmctldEvents(ObjectEvents):
    """Slurmctld emitted events."""

    slurm_config_available = EventSource(
        SlurmConfigAvailableEvent
    )
    slurm_configurator_available = EventSource(
        SlurmConfiguratorAvailableEvent
    )
    slurm_configurator_unavailable = EventSource(
        SlurmConfiguratorUnAvailableEvent
    )
    munge_key_available = EventSource(
        MungeKeyAvailableEvent
    )
    restart_slurmctld = EventSource(
        RestartSlurmctldEvent
    )
    scontrol_reconfigure = EventSource(
        ScontrolReconfigureEvent
    )
    scontrol_update = EventSource(
        ScontrolUpdateEvent
    )


class Slurmctld(Object):
    """Slurmctld."""

    _stored = StoredState()
    on = SlurmctldEvents()

    def __init__(self, charm, relation_name):
        """Set initial data and observe interface events."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self._stored.set_default(
            slurm_config=dict(),
            munge_key=str(),
            jwt_rsa=str(),
            restart_slurmctld_uuid=str(),
            scontrol_reconfigure_uuid=str(),
            scontrol_update_nodes=[]
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed,
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_departed,
            self._on_relation_departed,
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken,
        )

    def _on_relation_changed(self, event):
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            event.defer()
            return

        restart_slurmctld_uuid = event_app_data.get("restart_slurmctld_uuid")
        scontrol_reconfigure_uuid = event_app_data.get("scontrol_reconfigure_uuid")
        scontrol_update_nodes = event_app_data.get("scontrol_update_nodes")

        if restart_slurmctld_uuid:
            if restart_slurmctld_uuid != self._get_restart_slurmctld_uuid():
                self._store_restart_slurmctld_uuid(restart_slurmctld_uuid)
                self.on.restart_slurmctld.emit()

        if scontrol_reconfigure_uuid:
            if scontrol_reconfigure_uuid != self._get_scontrol_reconfigure_uuid():
                self._store_scontrol_reconfigure_uuid(scontrol_reconfigure_uuid)
                self.on.scontrol_reconfigure.emit()

        if scontrol_update_nodes:
            # we don't need to copare this list with a previous value, because
            # all nodes start with new_node = True, and when we run an action
            # to enlist them, slurm-configurator assembles a list of configured
            # nodes. We already did the accounting in slurm-configurator.
            nodes_list = list(literal_eval(scontrol_update_nodes))
            self._stored.scontrol_update_nodes = nodes_list
            self.on.scontrol_update.emit()
            logger.debug(f"### Slurmctld - peer - updated node list to update:"
                         f"{nodes_list}")

    def _on_relation_departed(self, event):
        self.on.slurm_configurator_unavailable.emit()

    def _on_relation_broken(self, event):
        self.set_slurmctld_info_on_app_relation_data("")
        self.on.slurm_configurator_unavailable.emit()

    @property
    def nodes_to_update(self):
        """Get list of nodes that are ready to be resumed."""
        return self._stored.scontrol_update_nodes

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    @property
    def is_joined(self):
        """Return True if self._relation is not None."""
        return self._relation is not None

    def set_slurmctld_info_on_app_relation_data(self, slurmctld_info):
        """Set slurmctld_info."""
        relations = self.framework.model.relations["slurmctld"]
        # Iterate over each of the relations setting the relation data.
        for relation in relations:
            if slurmctld_info != "":
                relation.data[self.model.app]["slurmctld_info"] = json.dumps(
                    slurmctld_info
                )
            else:
                relation.data[self.model.app]["slurmctld_info"] = ""

    def _get_slurm_config_from_relation(self):
        """Return slurm_config."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                app_data = relation.data.get(app)
                if app_data:
                    if app_data.get("slurm_config"):
                        return json.loads(app_data["slurm_config"])

        logger.warning("### slurmctdl - interface-slurmctld - "
                       "get_slurm_config_from_relation got nothing")
        return None

    def _store_restart_slurmctld_uuid(self, restart_slurmctld_uuid):
        self._stored.restart_slurmctld_uuid = restart_slurmctld_uuid

    def _get_restart_slurmctld_uuid(self):
        return self._stored.restart_slurmctld_uuid

    def _store_scontrol_reconfigure_uuid(self, scontrol_reconfigure_uuid):
        self._stored.scontrol_reconfigure_uuid = scontrol_reconfigure_uuid

    def _get_scontrol_reconfigure_uuid(self):
        return self._stored.scontrol_reconfigure_uuid
