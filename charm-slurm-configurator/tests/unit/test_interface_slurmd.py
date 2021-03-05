import copy
import pprint

from src.interface_slurmd import ensure_unique_partitions

# our "mock" of utils.get_inventory
# plus the new_node entry, which is crafted in charm-slurmd
# slurm-configurator inventory does not have this key
def get_inventory(name, addr):
    return {'node_name': name,
            'node_addr': addr,
            'state': 'UNKNOWN',
            'real_memory': '1955',
            'cpus': '2',
            'threads_per_core': '2',
            'cores_per_socket': '1',
            'sockets_per_board': '1',
            'new_node': True}


class TestSlurmd:
    pp = pprint.PrettyPrinter(indent=4)

    def test_ensure_unique_partitions_empty_list(self):
        assert ensure_unique_partitions([]) == []

    def test_ensure_unique_partitions_single_partition(self):
        base_partition = {"inventory": [get_inventory("name", "addr")],
                          "partition_name": "compute",
                          "partition_state": "IDLE",
                          "partition_config": ""}
        partitions = [base_partition.copy()]

        result = ensure_unique_partitions(copy.deepcopy(partitions))
        assert result == partitions

    def test_ensure_unique_partitions_single_partition_2_inventories(self):
        base_partition = {"inventory": [get_inventory("name", "addr"),
                                        get_inventory("name2", "addr2")],
                          "partition_name": "compute",
                          "partition_state": "IDLE",
                          "partition_config": ""}
        partitions = [base_partition.copy()]

        result = ensure_unique_partitions(copy.deepcopy(partitions))
        assert result == partitions

    def test_ensure_unique_partitions_single_partition_repeat_inventories(
            self):
        inv = get_inventory("name", "addr")
        base_partition = [{"inventory": [inv],
                           "partition_name": "compute",
                           "partition_state": "IDLE",
                           "partition_config": ""}]
        partition_2 = [{"inventory": [inv.copy(), inv.copy()],
                        "partition_name": "compute",
                        "partition_state": "IDLE",
                        "partition_config": ""}]

        result = ensure_unique_partitions(copy.deepcopy(partition_2))
        assert result == base_partition
