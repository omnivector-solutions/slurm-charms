#!/usr/bin/python3
"""utils.py module for slurmd charm."""
import json
import os
import random
import subprocess
import sys


def lscpu():
    """Return lscpu as a python dictionary."""
    def format_key(lscpu_key):
        key_lower = lscpu_key.lower()
        replace_hyphen = key_lower.replace("-", "_")
        replace_lparen = replace_hyphen.replace("(", "")
        replace_rparen = replace_lparen.replace(")", "")
        return replace_rparen.replace(" ", "_")

    lscpu_out = subprocess.check_output(['lscpu'])
    lscpu_lines = lscpu_out.decode().strip().split("\n")

    return {
        format_key(line.split(":")[0].strip()): line.split(":")[1].strip()
        for line in lscpu_lines
    }


def cpu_info():
    """Return cpu info needed to generate node inventory."""
    ls_cpu = lscpu()

    return {
        'cpus': ls_cpu['cpus'],
        'threads_per_core': ls_cpu['threads_per_core'],
        'cores_per_socket': ls_cpu['cores_per_socket'],
        'sockets_per_board': ls_cpu['sockets'],
    }


def free_m():
    """Return the real memory."""
    real_mem = ""
    try:
        real_mem = subprocess.check_output(
            "free -m | grep -oP '\\d+' | head -n 1",
            shell=True
        )
    except subprocess.CalledProcessError as e:
        print(e)
        sys.exit(-1)

    return real_mem.decode().strip()


def lspci_nvidia():
    """Check for and return the count of nvidia gpus."""
    gpus = 0
    try:
        gpus = int(
            subprocess.check_output(
                "lspci | grep -i nvidia | awk '{print $1}' "
                "| cut -d : -f 1 | sort -u | wc -l",
                shell=True
            ).decode().strip()
        )
    except subprocess.CalledProcessError as e:
        print(e)
        sys.exit(-1)

    for graphics_processing_unit in range(gpus):
        gpu_path = "/dev/nvidia" + str(graphics_processing_unit)
        if not os.path.exists(gpu_path):
            return 0
    return gpus


def get_inventory(node_name, node_addr):
    """Assemble and return the node info."""
    inventory = {
        'node_name': node_name,
        'node_addr': node_addr,
        'state': "UNKNOWN",
        'real_memory': free_m(),
        **cpu_info(),
    }

    gpus = lspci_nvidia()
    if (gpus > 0):
        inventory['gres'] = gpus
    return inventory


def _related_units(relid):
    """List of related units."""
    units_cmd_line = ['relation-list', '--format=json', '-r', relid]
    return json.loads(
        subprocess.check_output(units_cmd_line).decode('UTF-8')) or []


def _relation_ids(reltype):
    """List of relation_ids."""
    relid_cmd_line = ['relation-ids', '--format=json', reltype]
    return json.loads(
        subprocess.check_output(relid_cmd_line).decode('UTF-8')) or []


def get_active_units(relation_name):
    """Return the active_units."""
    active_units = []
    for rel_id in _relation_ids(relation_name):
        for unit in _related_units(rel_id):
            active_units.append(unit)
    return active_units


def random_string(length=10):
    """Generate a random string."""
    random_str = ""
    for i in range(length):
        random_integer = random.randint(97, 97 + 26 - 1)
        flip_bit = random.randint(0, 1)
        random_integer = \
            random_integer - 32 if flip_bit == 1 else random_integer
        random_str += (chr(random_integer))
    return random_str
