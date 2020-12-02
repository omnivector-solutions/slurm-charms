#!/usr/bin/python3
"""SlurmctldCharm."""
import copy
import logging

from interface_elasticsearch import Elasticsearch
from interface_grafana_source import GrafanaSource
from interface_influxdb import InfluxDB
from interface_nhc import Nhc
from interface_prolog_epilog import PrologEpilog
from interface_slurmctld import Slurmctld
from interface_slurmd import Slurmd
from interface_slurmdbd import Slurmdbd
from interface_slurmrestd import Slurmrestd
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmManager


logger = logging.getLogger()


class SlurmConfiguratorCharm(CharmBase):
    """Facilitate slurm configuration operations."""

    _stored = StoredState()

    def __init__(self, *args):
        """Init charm, _stored defaults, interfaces and observe events."""
        super().__init__(*args)

        self._stored.set_default(
            default_partition=str(),
            munge_key=str(),
            slurm_installed=False,
            slurmctld_available=False,
            slurmdbd_available=False,
            slurmd_available=False,
            slurmrestd_available=False,

        )

        self._elasticsearch = Elasticsearch(self, "elasticsearch")
        self._grafana = GrafanaSource(self, "grafana-source")
        self._influxdb = InfluxDB(self, "influxdb-api")
        self._nhc = Nhc(self, "nhc")
        self._slurmrestd = Slurmrestd(self, "slurmrestd")
        self._slurm_manager = SlurmManager(self, "slurmd")
        self._slurmctld = Slurmctld(self, "slurmctld")
        self._slurmdbd = Slurmdbd(self, "slurmdbd")
        self._slurmd = Slurmd(self, "slurmd")
        self._prolog_epilog = PrologEpilog(self, "prolog-epilog")

        # #### Charm lifecycle events #### #
        event_handler_bindings = {
            # #### Juju lifecycle events #### #
            self.on.install: self._on_install,

            # self.on.start:
            # self._on_check_status_and_write_config,

            self.on.config_changed:
            self._on_check_status_and_write_config,

            self.on.upgrade_charm: self._on_upgrade,

            # ######## Addons lifecycle events ######## #
            self._elasticsearch.on.elasticsearch_available:
            self._on_check_status_and_write_config,

            self._elasticsearch.on.elasticsearch_unavailable:
            self._on_check_status_and_write_config,

            self._grafana.on.grafana_available:
            self._on_grafana_available,

            self._influxdb.on.influxdb_available:
            self._on_influxdb_available,

            self._influxdb.on.influxdb_unavailable:
            self._on_check_status_and_write_config,

            self._nhc.on.nhc_bin_available:
            self._on_check_status_and_write_config,

            # ######## Slurm component lifecycle events ######## #
            self._slurmctld.on.slurmctld_available:
            self._on_check_status_and_write_config,

            self._slurmctld.on.slurmctld_unavailable:
            self._on_check_status_and_write_config,

            self._slurmdbd.on.slurmdbd_available:
            self._on_check_status_and_write_config,

            self._slurmdbd.on.slurmdbd_unavailable:
            self._on_check_status_and_write_config,

            self._slurmd.on.slurmd_available:
            self._on_check_status_and_write_config,

            self._slurmd.on.slurmd_unavailable:
            self._on_check_status_and_write_config,

            self._slurmrestd.on.slurmrestd_available:
            self._on_check_status_and_write_config,

            self._slurmrestd.on.slurmrestd_unavailable:
            self._on_check_status_and_write_config,

            self._prolog_epilog.on.prolog_epilog_available:
            self._on_check_status_and_write_config,

            self._prolog_epilog.on.prolog_epilog_unavailable:
            self._on_check_status_and_write_config,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        """Install the slurm snap and set the munge key."""
        self._slurm_manager.install()
        self._stored.munge_key = self._slurm_manager.get_munge_key()
        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("Slurm Installed")

    def _on_upgrade(self, event):
        """Upgrade the charm."""
        slurm_config = self._assemble_slurm_config()

        if not slurm_config:
            self.unit.status = BlockedStatus(
                "Cannot generate slurm_config, defering upgrade."
            )
            event.defer()
            return

        self._slurm_manager.upgrade(slurm_config)

    def _on_grafana_available(self, event):
        """Create the grafana-source if we are the leader and have influxdb."""
        leader = self._is_leader()
        influxdb_info = self._get_influxdb_info()
        grafana = self._grafana

        if leader and influxdb_info:
            grafana.set_grafana_source_info(influxdb_info)

    def _on_influxdb_available(self, event):
        """Create the grafana-source if we have all the things."""
        grafana = self._grafana
        influxdb_info = self._get_influxdb_info()
        leader = self._is_leader()

        if leader and grafana.is_joined and influxdb_info:
            grafana.set_grafana_source_info(influxdb_info)

        self._on_check_status_and_write_config(event)

    def _on_check_status_and_write_config(self, event):
        """Check that we have what we need before we proceed."""
        if not self._check_status():
            event.defer()
            return

        # Generate the slurm_config
        slurm_config = self._assemble_slurm_config()

        if not slurm_config:
            self.unit.status = BlockedStatus(
                "Cannot generate slurm_config - defering event."
            )
            event.defer()
            return

        self._slurmctld.set_slurm_config_on_app_relation_data(
            slurm_config,
        )
        self._slurmd.set_slurm_config_on_app_relation_data(
            slurm_config,
        )
        if self._stored.slurmrestd_available:
            self._slurmrestd.set_slurm_config_on_app_relation_data(
                slurm_config,
            )
        self._slurm_manager.render_config_and_restart(
            {**slurm_config, 'munge_key': self.get_munge_key()}
        )

    def _assemble_slurm_config(self):
        """Assemble and return the slurm config."""
        slurmctld_info = self._slurmctld.get_slurmctld_info()
        slurmdbd_info = self._slurmdbd.get_slurmdbd_info()
        slurmd_info = self._slurmd.get_slurmd_info()

        if not (slurmd_info and slurmctld_info and slurmdbd_info):
            return {}

        addons_info = self._assemble_addons()
        partitions_info = self._assemble_partitions(slurmd_info)

        logger.debug(addons_info)
        logger.debug(partitions_info)
        logger.debug(slurmctld_info)
        logger.debug(slurmdbd_info)

        return {
            'munge_key': self._stored.munge_key,
            'partitions': partitions_info,
            **slurmctld_info,
            **slurmdbd_info,
            **addons_info,
            **self.model.config,
        }

    def _assemble_partitions(self, slurmd_info):
        """Make any needed modifications to partition data."""
        slurmd_info_tmp = copy.deepcopy(slurmd_info)

        for partition in slurmd_info:

            # Deep copy the partition to a tmp var so we can modify it as
            # needed whilst not modifying the object we are iterating over.
            partition_tmp = copy.deepcopy(partition)
            # Extract the partition_name from the partition and from the charm
            # config.
            partition_name = partition['partition_name']
            default_partition_from_config = self.model.config.get(
                'default_partition'
            )

            # Check that the default_partition isn't defined in the charm
            # config.
            # If the user hasn't provided a default partition, then we infer
            # the partition_default by defaulting to the first related slurmd
            # application.
            if not default_partition_from_config:
                if partition['partition_name'] ==\
                   self._stored.default_partition:
                    partition_tmp['partition_default'] = 'YES'
            else:
                if default_partition_from_config == partition_name:
                    partition_tmp['partition_default'] = 'YES'

            slurmd_info_tmp.remove(partition)
            slurmd_info_tmp.append(partition_tmp)

        return slurmd_info_tmp

    def _assemble_addons(self):
        """Assemble any addon components."""
        acct_gather = self._get_influxdb_info()
        elasticsearch_ingress = \
            self._elasticsearch.get_elasticsearch_ingress()
        nhc_info = self._nhc.get_nhc_info()
        prolog_epilog = self._prolog_epilog.get_prolog_epilog()

        ctxt = dict()

        if prolog_epilog:
            ctxt['prolog_epilog'] = prolog_epilog

        if acct_gather:
            ctxt['acct_gather'] = acct_gather
            acct_gather_custom = self.model.config.get('acct_gather_custom')
            if acct_gather_custom:
                ctxt['acct_gather']['custom'] = acct_gather_custom

        if nhc_info:
            ctxt['nhc'] = {
                'nhc_bin': nhc_info['nhc_bin'],
                'health_check_interval': nhc_info['health_check_interval'],
                'health_check_node_state': nhc_info['health_check_node_state'],
            }

        if elasticsearch_ingress:
            ctxt['elasticsearch_address'] = elasticsearch_ingress

        return ctxt

    def _check_status(self):
        """Check that the core components we need exist."""
        slurmctld_available = self._stored.slurmctld_available
        slurmdbd_available = self._stored.slurmdbd_available
        slurmd_available = self._stored.slurmd_available
        slurm_installed = self._stored.slurm_installed
        default_partition = self._stored.default_partition

        deps = [
            default_partition,
            slurmctld_available,
            slurmdbd_available,
            slurmd_available,
            slurm_installed,
        ]

        if not all(deps):
            if not slurmctld_available:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMCTLD")
            elif not slurmdbd_available:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMDBD")
            elif not slurmd_available:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMD")
            elif not slurm_installed:
                self.unit.status = BlockedStatus("SLURM NOT INSTALLED")
            else:
                self.unit.status = BlockedStatus("PARTITION NAME UNAVAILABLE")
            return False
        else:
            self.unit.status = ActiveStatus("")
            return True

    def _get_influxdb_info(self):
        """Return influxdb info."""
        return self._influxdb.get_influxdb_info()

    def _is_leader(self):
        return self.model.unit.is_leader()

    def get_munge_key(self):
        """Return the slurmdbd_info from stored state."""
        return self._stored.munge_key

    def get_default_partition(self):
        """Return self._stored.default_partition."""
        return self._stored.default_partition

    def is_slurm_installed(self):
        """Return true/false based on whether or not slurm is installed."""
        return self._stored.slurm_installed

    def set_slurmctld_available(self, slurmctld_available):
        """Set slurmctld_available."""
        self._stored.slurmctld_available = slurmctld_available

    def set_slurmdbd_available(self, slurmdbd_available):
        """Set slurmdbd_available."""
        self._stored.slurmdbd_available = slurmdbd_available

    def set_default_partition(self, partition_name):
        """Set self._stored.default_partition."""
        self._stored.default_partition = partition_name

    def set_slurmd_available(self, slurmd_available):
        """Set slurmd_available."""
        self._stored.slurmd_available = slurmd_available

    def set_slurmrestd_available(self, slurmrestd_available):
        """Set slurmrestd_available."""
        self._stored.slurmrestd_available = slurmrestd_available


if __name__ == "__main__":
    main(SlurmConfiguratorCharm)
