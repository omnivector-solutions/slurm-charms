import copy
import pprint

from src.interface_slurmd import Slurmd
from src.utils import get_inventory


class TestSlurmd:
    pp = pprint.PrettyPrinter(indent=4)

    def test_ensure_unique_partitions_empty_list(self):
        assert Slurmd.ensure_unique_partitions([]) == []

    def test_ensure_unique_partitions_single_partition(self):
        base_partition = {"inventory": [get_inventory("name", "addr")],
                          "partition_name": "compute",
                          "partition_state": "IDLE",
                          "partition_config": ""}
        partitions = [base_partition.copy()]

        result = Slurmd.ensure_unique_partitions(copy.deepcopy(partitions))
        assert result == partitions

    def test_ensure_unique_partitions_single_partition_2_inventories(self):
        base_partition = {"inventory": [get_inventory("name", "addr"),
                                        get_inventory("name2", "addr2")],
                          "partition_name": "compute",
                          "partition_state": "IDLE",
                          "partition_config": ""}
        partitions = [base_partition.copy()]

        result = Slurmd.ensure_unique_partitions(copy.deepcopy(partitions))
        assert result == partitions

    def test_ensure_unique_partitions_single_partition_repeat_inventories(self):
        inv = get_inventory("name", "addr")
        base_partition = [{"inventory": [inv],
                          "partition_name": "compute",
                          "partition_state": "IDLE",
                          "partition_config": ""}]
        partition_2 = [{"inventory": [inv.copy(), inv.copy()],
                        "partition_name": "compute",
                        "partition_state": "IDLE",
                        "partition_config": ""}]

        result = Slurmd.ensure_unique_partitions(copy.deepcopy(partition_2))
        assert result == base_partition

