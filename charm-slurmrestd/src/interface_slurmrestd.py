#!/usr/bin/env python3
"""SlurmrestdRequiries."""
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


class SlurmrestdAvailableEvent(EventBase):
    """SlurmctldAvailableEvent."""


class SlurmrestdUnavailableEvent(EventBase):
    """SlurmctldUnavailableEvent."""


class MungeKeyAvailableEvent(EventBase):
    """MungeKeyAvailableEvent."""


class JwtRsaAvailableEvent(EventBase):
    """JwtRsaAvailableEvent."""


class RestartSlurmrestdEvent(EventBase):
    """RestartSlurmrestdEvent."""


class SlurmrestdEvents(ObjectEvents):
    """SlurmLoginEvents."""

    config_available = EventSource(SlurmrestdAvailableEvent)
    config_unavailable = EventSource(SlurmrestdUnavailableEvent)
    munge_key_available = EventSource(MungeKeyAvailableEvent)
    jwt_rsa_available = EventSource(JwtRsaAvailableEvent)
    restart_slurmrestd = EventSource(RestartSlurmrestdEvent)


class SlurmrestdRequires(Object):
    """SlurmrestdRequires."""

    _stored = StoredState()
    on = SlurmrestdEvents()

    def __init__(self, charm, relation_name):
        """Set the provides initial data."""
        super().__init__(charm, relation_name)

        self._charm = charm
        self._relation_name = relation_name

        self._stored.set_default(
            munge_key=str(),
            jwt_rsa=str(),
            slurm_config=dict(),
            restart_slurmrestd_uuid=str(),
        )

        self.framework.observe(
            self._charm.on[relation_name].relation_joined,
            self._on_relation_joined
        )
        self.framework.observe(
            self._charm.on[relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            self._charm.on[relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_joined(self, event):
        """Get the munge/jwt keys from slurmctld on relation joined."""
        # Since we are in relation-joined (with the app on the other side)
        # we can almost guarantee that the app object will exist in
        # the event, but check for it just in case.
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            event.defer()
            return

        # slurmctld sets the munge_key on the relation-created event
        # which happens before relation-joined. We can almost guarantee that
        # the munge key will exist at this point, but check for it just incase.
        munge_key = event_app_data.get("munge_key")
        if not munge_key:
            event.defer()
            return

        jwt_rsa = event_app_data.get("jwt_rsa")
        if not jwt_rsa:
            event.defer()
            return

        # Store the keys in the charm's state
        self._store_munge_key(munge_key)
        self._store_jwt_rsa(jwt_rsa)
        self.on.munge_key_available.emit()
        self.on.jwt_rsa_available.emit()

    def _on_relation_changed(self, event):
        """Check for the munge_key in the relation data."""
        event_app_data = event.relation.data.get(event.app)
        if not event_app_data:
            event.defer()
            return

        munge_key = event_app_data.get('munge_key')
        jwt_rsa = event_app_data.get('jwt_rsa')
        restart_slurmrestd_uuid = event_app_data.get("restart_slurmrestd_uuid")
        slurm_config = self._get_slurm_config_from_relation()

        if not (munge_key and slurm_config):
            event.defer()
            return

        # Store the munge_key in the interface StoredState if it has changed
        if munge_key != self.get_stored_munge_key():
            self._store_munge_key(munge_key)
            self.on.munge_key_available.emit()

        # Store the jwt_rsa in the interface StoredState if it has changed
        if jwt_rsa != self.get_stored_jwt_rsa():
            self._store_jwt_rsa(jwt_rsa)
            self.on.jwt_rsa_available.emit()

        # Store the slurm_config in the interface StoredState if it has changed
        if slurm_config != self.get_stored_slurm_config():
            self._store_slurm_config(slurm_config)
            self.on.config_available.emit()

        if restart_slurmrestd_uuid:
            if restart_slurmrestd_uuid != self._get_restart_slurmrestd_uuid():
                self._store_restart_slurmrestd_uuid(restart_slurmrestd_uuid)
                self.on.restart_slurmrestd.emit()

    def _on_relation_broken(self, event):
        self.on.config_unavailable.emit()

    def _get_slurm_config_from_relation(self):
        """Return slurm_config."""
        relation = self._relation
        if relation:
            app = relation.app
            if app:
                app_data = self._relation.data.get(app)
                if app_data:
                    slurm_config = app_data.get('slurm_config')
                    if slurm_config:
                        return json.loads(slurm_config)
        return None

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    @property
    def is_joined(self):
        """Return True if relation is joined."""
        return self._relation is not None

    def _store_restart_slurmrestd_uuid(self, restart_slurmrestd_uuid):
        self._stored.restart_slurmrestd_uuid = restart_slurmrestd_uuid

    def _get_restart_slurmrestd_uuid(self):
        return self._stored.restart_slurmrestd_uuid

    def _store_munge_key(self, munge_key):
        self._stored.munge_key = munge_key

    def get_stored_munge_key(self):
        """Retrieve the munge_key from stored state."""
        return self._stored.munge_key

    def _store_jwt_rsa(self, jwt_rsa):
        self._stored.jwt_rsa = jwt_rsa

    def get_stored_jwt_rsa(self):
        """Retrieve the jwt_rsa from stored state."""
        return self._stored.jwt_rsa

    def _store_slurm_config(self, slurm_config):
        self._stored.slurm_config = slurm_config

    def get_stored_slurm_config(self):
        """Retrieve the slurm_config from stored state."""
        return self._stored.slurm_config
