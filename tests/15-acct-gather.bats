#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"


myjuju () {
	juju "$@"
	juju-wait -t 540 -m $JUJU_MODEL
}


@test "Assert we can update JobAcctGatherFrequency" {
	freq="task=$RANDOM"
	myjuju config slurmctld acct-gather-frequency="$freq"
	# we need to wait scontrol reconfigure to finish, this is not reflected
	# on Juju status
	sleep 5

	run juju run --unit slurmctld/leader "grep JobAcctGatherFrequency /etc/slurm/slurm.conf"
	assert_output "JobAcctGatherFrequency=$freq"

	run juju run --unit slurmd/leader "grep JobAcctGatherFrequency /run/slurm/conf/slurm.conf"
	assert_output "JobAcctGatherFrequency=$freq"
}
