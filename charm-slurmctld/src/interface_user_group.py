from ops.framework import EventBase, EventSource, Object, ObjectEvents


class CreateUserGroupEvent(EventBase):
    """Event to signal the creation of a user/group."""

class RemoveUserGroupEvent(EventBase):
    """Event to signal the removal of a user/group."""


class UserGroupEvents(ObjectEvents):
    """UserGroupEvents."""

    create_user_group = EventSource(CreateUserGroupEvent)
    remove_user_group = EventSource(RemoveUserGroupEvent)


class UserGroupRequires(Object):

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
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken,
        )

    @property
    def _relation(self):
        return self.framework.model.get_relation(self._relation_name)

    def _on_relation_joined(self, event):
        """Create the user and group sent by the provides side of the relation."""
        self.on.create_user_group.emit()

    def _on_relation_broken(self, event):
        """Remove the user and group."""
        self.on.remove_user_group.emit()

    def get_user_group(self):
        app_relation_data = self._relation.data[event.app]
        user_name = app_relation_data["user_name"]
        group_name = app_relation_data["group_name"]
        return user_name, group_name
