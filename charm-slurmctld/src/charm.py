#!/usr/bin/env python3
"""SlurmctldCharm."""
import logging
import shlex
import subprocess

from interface_slurmctld import Slurmctld
from interface_slurmctld_peer import SlurmctldPeer
from nrpe_external_master import Nrpe
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
            slurm_configurator_available=False,
            slurmctld_controller_type=str(),
            slurm_installed=False,
        )

        self._nrpe = Nrpe(self, "nrpe-external-master")

        self._slurm_manager = SlurmManager(self, "slurmctld")

        self._slurmctld = Slurmctld(self, "slurmctld")
        self._slurmctld_peer = SlurmctldPeer(self, "slurmctld-peer")

        event_handler_bindings = {
            self.on.install: self._on_install,
            self._slurmctld.on.slurm_config_available:
            self._on_check_status_and_write_config,
            self._slurmctld.on.scontrol_reconfigure:
            self._on_scontrol_reconfigure,
            self._slurmctld.on.restart_slurmctld: self._on_restart_slurmctld,
            self._slurmctld.on.slurm_configurator_available:
            self._on_provision_keys,
            self._slurmctld_peer.on.slurmctld_peer_available:
            self._on_slurmctld_peer_available,
            # ations
            self.on.drain_action: self._drain_nodes_action,
            self.on.resume_action: self._resume_nodes_action,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self._slurm_manager.install()
        self._stored.slurm_installed = True
        self.unit.status = ActiveStatus("slurm successfully installed")

        self._slurm_manager.start_munged()

    def _on_provision_keys(self, event):
        if not self._stored.slurm_installed:
            event.defer()
            return

        # Retrieve the munge_key and jwt_rsa from the slurm-configurator
        munge_key = self._slurmctld.get_stored_munge_key()
        jwt_rsa = self._slurmctld.get_stored_jwt_rsa()

        # Write the keys to their respective locations in the filesystem
        self._slurm_manager.configure_munge_key(munge_key)
        self._slurm_manager.configure_jwt_rsa(jwt_rsa)

        self._slurm_manager.restart_munged()
        self._stored.slurm_configurator_available = True

    def _on_slurmctld_peer_available(self, event):
        if self.framework.model.unit.is_leader():
            if self._slurmctld.is_joined:
                slurmctld_info = self._slurmctld_peer.get_slurmctld_info()
                if slurmctld_info:
                    self._slurmctld.set_slurmctld_info_on_app_relation_data(
                        slurmctld_info
                    )
                    return
            event.defer()
            return

    def _on_check_status_and_write_config(self, event):
        slurm_config = self._check_status()
        if not slurm_config:
            event.defer()
            return

        self._slurm_manager.render_slurm_configs(dict(slurm_config))
        self.unit.status = ActiveStatus("slurmctld available")

    def _on_restart_slurmctld(self, event):
        self._slurm_manager.restart_slurm_component()

    def _on_scontrol_reconfigure(self, event):
        if not self._stored.slurm_installed:
            event.defer()
        else:
            self._slurm_manager.slurm_cmd("scontrol", "reconfigure")

    def _on_scontrol_update(self, event):
        """Run scontrol update nodename=node state=resume for each node."""
        nodes = self._slurmctld.nodes_to_update
        for node in nodes:
            update = f"update nodename={node} state=resume"
            logger.debug(f"### slurctld - scontrol {update}")
            self._slurm_manager.slurm_cmd("scontrol", update)

    def _check_status(self):
        slurm_configurator_available = self._stored.slurm_configurator_available
        slurm_installed = self._stored.slurm_installed
        slurm_config = self._slurmctld.get_stored_slurm_config()

        components = [slurm_configurator_available,
                      slurm_installed,
                      slurm_config]

        slurmctld_joined = self._slurmctld.is_joined

        if not slurmctld_joined:
            self.unit.status = BlockedStatus(
                "Relations needed: slurm-configurator"
            )
            return None

        if not all(components):
            self.unit.status = WaitingStatus("Waiting on: configuration")
            return None

        return slurm_config

    def _drain_nodes_action(self, event):
        """Drain specified nodes."""
        nodes = event.params['nodename']
        reason = event.params['reason']

        logger.debug(f'#### Draining {nodes} because {reason}.')
        event.log(f'Draining {nodes} because {reason}.')

        try:
            cmd = f'scontrol update nodename={nodes} state=drain reason="{reason}"'
            subprocess.check_output(shlex.split(cmd))
            event.set_results({'status': 'draining', 'nodes': nodes})
        except subprocess.CalledProcessError as e:
            event.fail(message=f'Error draining {nodes}: {e.output}')

    def _resume_nodes_action(self, event):
        """Resume specified nodes."""
        nodes = event.params['nodename']

        logger.debug(f'#### Resuming {nodes}.')
        event.log(f'Resuming {nodes}.')

        try:
            cmd = f'scontrol update nodename={nodes} state=resume'
            subprocess.check_output(shlex.split(cmd))
            event.set_results({'status': 'resuming', 'nodes': nodes})
        except subprocess.CalledProcessError as e:
            event.fail(message=f'Error resuming {nodes}: {e.output}')

    def get_slurm_component(self):
        """Return the slurm component."""
        return self._slurm_manager.slurm_component

    def get_hostname(self):
        """Return the hostname."""
        return self._slurm_manager.hostname

    def get_port(self):
        """Return the port."""
        return self._slurm_manager.port


if __name__ == "__main__":
    main(SlurmctldCharm)
