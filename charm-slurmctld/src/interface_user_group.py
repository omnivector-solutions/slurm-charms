#!/usr/bin/env python3
"""User-Group interface."""
from ops.framework import EventBase, EventSource, Object, ObjectEvents


class CreateUserGroupEvent(EventBase):
    """Event to signal the creation of a user/group."""


class RemoveUserGroupEvent(EventBase):
    """Event to signal the removal of a user/group."""


class UserGroupEvents(ObjectEvents):
    """UserGroupEvents."""

    create_user_group = EventSource(CreateUserGroupEvent)
    remove_user_group = EventSource(RemoveUserGroupEvent)


class UserGroupProvides(Object):
    """UserGroup Interface."""

    on = UserGroupEvents()

    def __init__(self, charm, relation_name):
        """Observe relation events."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            self._charm.on[self._relation_name].relation_joined,
            self._on_relation_joined,
        )

        self.framework.observe(
            self._charm.on[self._relation_name].relation_departed,
            self._on_relation_departed,
        )

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    def _on_relation_joined(self, event):
        """Create the user and group sent by the provides side of the relation."""
        app_data = event.relation.data.get(event.app)

        self.user_name = app_data.get("user_name")
        if not app_data.get("user_uid"):
            event.defer()
            return
        self.user_uid = app_data.get("user_uid")
        self.group_name = app_data.get("group_name")

        self.on.create_user_group.emit()

    def _on_relation_departed(self, event):
        """Remove the user and group."""
        app_data = event.relation.data.get(event.app)

        self.user_name = app_data.get("user_name")
        if not app_data.get("user_uid"):
            event.defer()
            return
        self.user_uid = app_data.get("user_uid")
        self.group_name = app_data.get("group_name")

        self.on.remove_user_group.emit()
