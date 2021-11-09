"""Slurm Prolog and Epilog interface."""
import json
import logging

from ops.framework import EventBase, EventSource, Object, ObjectEvents, StoredState

logger = logging.getLogger()


class PrologEpilogAvailableEvent(EventBase):
    """Emmited when the prolog and epilog are available."""


class PrologEpilogUnavailableEvent(EventBase):
    """Emmited when the prolog and epilog are unavailable."""


class SlurmPrologEpilogEvents(ObjectEvents):
    """Events for Prolog and Epilog."""

    prolog_epilog_available = EventSource(PrologEpilogAvailableEvent)
    prolog_epilog_unavailable = EventSource(PrologEpilogUnavailableEvent)


class PrologEpilog(Object):
    """Epilog/prolog interface."""

    _stored = StoredState()
    on = SlurmPrologEpilogEvents()

    def __init__(self, charm, relation_name):
        """Set the initial data."""
        super().__init__(charm, relation_name)

        self._charm = charm
        self._stored.set_default(prolog_epilog=str())

        self.framework.observe(self._charm.on[relation_name].relation_changed,
                               self._on_relation_changed)
        self.framework.observe(self._charm.on[relation_name].relation_broken,
                               self._on_relation_broken)

    def _on_relation_changed(self, event):
        """Get the paths for the scripts and emit prolog_epilog_available."""
        prolog = event.relation.data[event.unit].get("prolog", None)
        epilog = event.relation.data[event.unit].get("epilog", None)

        logger.debug(f"## received: Prolog: {prolog}. Epilog: {epilog}.")

        if not (prolog and epilog):
            event.defer()
            logger.warning("## Missing one prolog or epilog. Deferring.")
            return

        self._stored.prolog_epilog = json.dumps({"slurmctld_epilog_path": epilog,
                                                 "slurmctld_prolog_path": prolog})

        self.on.prolog_epilog_available.emit()

    def _on_relation_broken(self, event):
        """Remove configured paths."""
        self._stored.prolog_epilog = str()
        self.on.prolog_epilog_unavailable.emit()

    def get_prolog_epilog(self) -> dict:
        """Return path of epilog and prolog.

        Output is a dictionary:
            {"slurmctld_epilog_path": "/path/to/executable"
             "slurmctld_prolog_path": "/path/to/executable"}
        """
        info = self._stored.prolog_epilog
        if info:
            return json.loads(info)
        else:
            return {}
