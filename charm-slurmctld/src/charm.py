#!/usr/bin/env python3
"""SlurmctldCharm."""
import copy
import logging
import shlex
import subprocess

from interface_slurmd import Slurmd
from interface_slurmdbd import Slurmdbd
from interface_slurmctld_peer import SlurmctldPeer
#from nrpe_external_master import Nrpe
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from slurm_ops_manager import SlurmManager

logger = logging.getLogger()


class SlurmctldCharm(CharmBase):
    """Slurmctld lifecycle events."""

    _stored = StoredState()

    def __init__(self, *args):
        """Init _stored attributes and interfaces, observe events."""
        super().__init__(*args)

        self._stored.set_default(
            slurmctld_controller_type=str(),
            slurm_installed=False,
        )

        self._slurm_manager = SlurmManager(self, "slurmctld")

        self._slurmd = Slurmd(self, "slurmd")
        self._slurmdbd = Slurmdbd(self, "slurmdbd")
        self._slurmctld_peer = SlurmctldPeer(self, "slurmctld-peer")


        event_handler_bindings = {
            self.on.install: self._on_install,

            self._slurmdbd.on.slurmdbd_available: self._on_write_slurm_config,
            self._slurmdbd.on.slurmdbd_unavailable: self._on_write_slurm_config,
            self._slurmd.on.slurmd_available: self._on_write_slurm_config,
            self._slurmd.on.slurmd_unavailable: self._on_write_slurm_config,
            self._slurmctld_peer.on.slurmctld_peer_available: self._on_write_slurm_config,

            self.on.debug_action: self._debug_action,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    @property
    def hostname(self):
        """Return the hostname."""
        return self._slurm_manager.hostname

    @property
    def port(self):
        """Return the port."""
        return self._slurm_manager.port

    @property
    def _slurmctld_info(self):
        return self._slurmctld_peer.get_slurmctld_info()

    @property
    def _slurmdbd_info(self):
        return self._slurmdbd.get_slurmdbd_info()

    @property
    def _slurmd_info(self):
        return self._slurmd.get_slurmd_info()

    def _debug_action(self, event):
        slurm_config = self._assemble_slurm_config()
        logger.debug(f"############ DEBUG FUNC RATS -> {slurm_config}")
        event.set_results({"slurmctld-info": slurm_config})

    def _on_install(self, event):
        """
        Perform installation operations for slurmctld.
        """
        logger.debug(f"######### ON_INSTALL: {self.on.__dict__}")

        #self._slurm_manager.install()

        # Store the munge_key and jwt_rsa key in the stored state.
        #
        # NOTE: Use leadership settings instead of stored state when
        # leadership settings support becomes available in the framework.
        #if self._is_leader():
        #    self._stored.jwt_rsa = self._slurm_manager.generate_jwt_rsa()
        #    self._stored.munge_key = self._slurm_manager.get_munge_key()

        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("slurm installed")

    def _assemble_partitions(self, slurmd_info):
        """Make any needed modifications to partition data."""
        slurmd_info_tmp = copy.deepcopy(slurmd_info)
        default_partition_from_config = self.config.get("default-partition")

        for partition in slurmd_info:
            # Deep copy the partition to a tmp var so we can modify it as
            # needed whilst not modifying the object we are iterating over.
            partition_tmp = copy.deepcopy(partition)
            # Extract the partition_name from the partition.
            partition_name = partition["partition_name"]

            # Check that the default_partition isn't defined in the charm
            # config.
            # If the user hasn't provided a default partition, then we infer
            # the partition_default by defaulting to the "configurator"
            # partition.
            if not default_partition_from_config:
                if partition["partition_name"] == "configurator":
                    partition_tmp["partition_default"] = "YES"
            else:
                if default_partition_from_config == partition_name:
                    partition_tmp["partition_default"] = "YES"

            slurmd_info_tmp.remove(partition)
            slurmd_info_tmp.append(partition_tmp)

        return slurmd_info_tmp

    def _assemble_slurm_config(self):
        """Assemble and return the slurm config."""
        slurmctld_info = self._slurmctld_info
        slurmdbd_info = self._slurmdbd_info
        slurmd_info = self._slurmd_info

        logger.debug("######## RATS INFO")
        logger.debug(slurmd_info)
        logger.debug(slurmctld_info)
        logger.debug(slurmdbd_info)
        
        if not (slurmctld_info and slurmd_info and slurmdbd_info):
            return {}

        #addons_info = self._assemble_addons()
        partitions_info = self._assemble_partitions(slurmd_info)
        #down_nodes = self._assemble_down_nodes(slurmd_info)

        #logger.debug(addons_info)
        logger.debug(partitions_info)
        logger.debug(slurmctld_info)
        logger.debug(slurmdbd_info)
        #logger.debug(f"#### _assemble_slurm_config() Down nodes: {down_nodes}")

        return {
            "partitions": partitions_info,
            #"down_nodes": down_nodes,
            **slurmctld_info,
            **slurmdbd_info,
            #**addons_info,
            #**self.config,
        }

    def _on_write_slurm_config(self, event):
        """Check that we have what we need before we proceed."""
        #if not self._check_status():
        #    event.defer()
        #    return

        logger.debug("### Slurmctld - _on_write_slurm_config()")

        # Generate the slurm_config
        slurm_config = self._assemble_slurm_config()
        logger.debug(f"####### WRITE SLURM CONFIG: {slurm_config}")
        return slurm_config

    def is_slurm_installed(self):
        """Return true/false based on whether or not slurm is installed."""
        return self._stored.slurm_installed


if __name__ == "__main__":
    main(SlurmctldCharm)
