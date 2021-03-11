from src.charm import SlurmConfiguratorCharm

# our "mock" of utils.get_inventory
# plus the new_node entry, which is crafted in charm-slurmd
# slurm-configurator inventory does not have this key
def get_inventory(name, addr, new_node=True):
    return {'node_name': name,
            'node_addr': addr,
            'state': 'UNKNOWN',
            'real_memory': '1955',
            'cpus': '2',
            'threads_per_core': '2',
            'cores_per_socket': '1',
            'sockets_per_board': '1',
            'new_node': new_node}

def empty_partition(name):
    return {"inventory": [],
            "partition_name": name,
            "partition_state": "INACTIVE",
            "partition_config": ""}

def configurator_partition():
    configurator = empty_partition('configurator')
    configurator["inventory"] = [get_inventory('configurator', 'add')]
    return configurator


#### tests of SlurmConfguratorCharm._assemble_down_nodes()

def test_assemble_down_nodes_empty():
    result = SlurmConfiguratorCharm._assemble_down_nodes([])
    assert result == []


def test_assemble_down_nodes_only_configurator():
    slurmd_info = [configurator_partition()]
    result = SlurmConfiguratorCharm._assemble_down_nodes(slurmd_info)
    assert result == []

def test_assemble_down_nodes_configurator_compute_login():
    login_partition = empty_partition('login')
    login_partition["inventory"].append(get_inventory('login-0', 0))
    login_partition["inventory"].append(get_inventory('login-1', 1))
    login_partition["inventory"].append(get_inventory('login-2', 2, False))

    compute_partition = empty_partition('compute')
    compute_partition["inventory"].append(get_inventory('compute-0', 0))
    compute_partition["inventory"].append(get_inventory('compute-1', 1))
    compute_partition["inventory"].append(get_inventory('compute-2', 2, False))
    compute_partition["inventory"].append(get_inventory('compute-3', 4, False))

    slurmd_info = [configurator_partition(),
                   login_partition,
                   compute_partition]

    result = SlurmConfiguratorCharm._assemble_down_nodes(slurmd_info)
    assert result == ['login-0', 'login-1', 'compute-0', 'compute-1']

