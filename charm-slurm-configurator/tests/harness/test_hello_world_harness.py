#!/usr/bin/env python3
"""
Use the operator framework test harness to test slurm-configurator.
"""
from ops.testing import Harness
from pytest import fixture

from src import charm


@fixture
def harness():
    """
    Use the ops framework test harness to drive
    """
    return Harness(charm.SlurmConfiguratorCharm)


def test_hello_world(harness):
    harness.begin()
    assert 1 == 1
