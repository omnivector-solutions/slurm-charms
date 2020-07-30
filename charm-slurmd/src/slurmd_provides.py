#!/usr/bin/env python3
"""provides interface for slurmd."""
import logging
import os
import re
import socket
import subprocess
import sys
import json


from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
    StoredState,
)


logger = logging.getLogger()


class ConfigAvailableEvent(EventBase):
    """ConfigAvailableEvent."""

class ConfigUnAvailableEvent(EventBase):
    """ConfigUnAvailableEvent."""

class SlurmdProvidesEvents(ObjectEvents):
    """Slurm Provides Events."""
    config_available = EventSource(ConfigAvailableEvent)
    config_unavailable = EventSource(ConfigUnAvailableEvent)


class SlurmdProvides(Object):
    """Provides the hostname, inventory, partions, default config to slurmctld.

    * on created:
        - sets the slurmd node info to the relation data
    * on changed:
        - retrieves the slurm_config from app data
        - stores the config to the charms stored state
        - signals config_available event for main charm to write config
   * on unavailable:
        - sets config_available to false
    """

    on = SlurmdProvidesEvents()
    _state = StoredState()

    def __init__(self, charm, relation_name):
        """Set self._relation_name and self.charm."""
        super().__init__(charm, relation_name)
        self.charm = charm
        self._relation_name = relation_name

        self._state.set_default(slurm_config=str())
        self._state.set_default(config_available=False)

        self.framework.observe(
            self.charm.on[self._relation_name].relation_created,
            self._on_relation_created
        )
        self.framework.observe(
            self.charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )
        self.framework.observe(
            self.charm.on[self._relation_name].relation_broken,
            self._on_relation_broken
        )

    def _on_relation_created(self, event):
        if self.charm._stored.slurm_installed:
            event.relation.data[self.model.unit]['hostname'] = get_hostname()
            event.relation.data[self.model.unit]['inventory'] = get_inventory()
            event.relation.data[self.model.unit]['partition'] = \
                self.charm.config['partition']
            event.relation.data[self.model.unit]['default'] = \
                str(self.charm.config['default']).lower()
        else:
            # If we hit this hook/handler before slurm is installed, defer.
            logger.debug("SLURM NOT INSTALLED DEFERING SETTING RELATION DATA")
            event.defer()
            return

    def _on_relation_changed(self, event):
        # Check that the app exists in the event
        if not event.relation.data.get(event.app):
            event.defer()
            return

        slurm_config = event.relation.data[event.app].get('slurm_config')
        # Check that slurm_config exists in the relation data
        # for the application.
        if not slurm_config:
            event.defer()
            return
        self.charm._stored.slurm_config = json.loads(slurm_config)
        self.charm._stored.config_available = True
        self.on.config_available.emit()

    def _on_relation_broken(self, event):
        self.charm._stored.config_available = False
        self.on.config_unavailable.emit()


def _get_real_mem():
    """Return the real memory."""
    try:
        real_mem = subprocess.check_output(
            "free -m | grep -oP '\\d+' | head -n 1",
            shell=True
        )
    except subprocess.CalledProcessError as e:
        # logger.debug(e)
        print(e)
        sys.exit(-1)

    return real_mem.decode().strip()


def _get_cpu_info():
    """Return the socket info."""
    try:
        lscpu = \
            subprocess.check_output(
                "lscpu",
                shell=True
            ).decode().replace("(s)", "")
    except subprocess.CalledProcessError as e:
        print(e)
        sys.exit(-1)

    cpu_info = {
        'CPU:': '',
        'Thread per core:': '',
        'Core per socket:': '',
        'Socket:': '',
    }

    try:
        for key in cpu_info:
            cpu_info[key] = re.search(f"{key}.*", lscpu)\
                              .group()\
                              .replace(f"{key}", "")\
                              .replace(" ", "")
    except Exception as error:
        print(f"Unable to set Node configuration: {error}")
        sys.exit(-1)

    return f"CPUs={cpu_info['CPU:']} "\
           f"ThreadsPerCore={cpu_info['Thread per core:']} "\
           f"CoresPerSocket={cpu_info['Core per socket:']} "\
           f"SocketsPerBoard={cpu_info['Socket:']}"


# Get the number of GPUs and check that they exist at /dev/nvidiaX
def _get_gpus():
    gpu = int(
        subprocess.check_output(
            "lspci | grep -i nvidia | awk '{print $1}' "
            "| cut -d : -f 1 | sort -u | wc -l",
            shell=True
        )
    )

    for i in range(gpu):
        gpu_path = "/dev/nvidia" + str(i)
        if not os.path.exists(gpu_path):
            return 0
    return gpu


def get_hostname():
    """Return the hostname."""
    return socket.gethostname().split(".")[0]


def get_inventory():
    """Assemble and return the node info."""
    hostname = get_hostname()
    mem = _get_real_mem()
    cpu_info = _get_cpu_info()
    gpus = _get_gpus()

    node_info = f"NodeName={hostname} "\
                f"NodeAddr={hostname} "\
                f"State=UNKNOWN "\
                f"{cpu_info} "\
                f"RealMemory={mem}"
    if (gpus > 0):
        node_info = node_info+f" Gres={gpus}"

    return node_info
