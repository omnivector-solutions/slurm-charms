#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"


@test "Assert we can update JobAcctGatherFrequency" {
	freq="task=$RANDOM"
	myjuju config slurmctld acct-gather-frequency="$freq"
	# we need to wait scontrol reconfigure to finish, this is not reflected
	# on Juju status
	sleep 5

	run juju run -m $JUJU_MODEL --unit slurmctld/leader "grep JobAcctGatherFrequency /etc/slurm/slurm.conf"
	assert_output "JobAcctGatherFrequency=$freq"

	run juju run -m $JUJU_MODEL --unit slurmd/leader "grep JobAcctGatherFrequency /run/slurm/conf/slurm.conf"
	assert_output "JobAcctGatherFrequency=$freq"
}

@test "Assert we can run-action influxdb-info" {
	run juju run-action -m $JUJU_MODEL slurmctld/leader influxdb-info --wait --format=json
	assert_output --partial "not related"
}
