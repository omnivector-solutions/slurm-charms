#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"

myjuju () {
	juju "$@"
	juju-wait -t 540 -m $JUJU_MODEL
}


@test "test first node is down" {
	run juju run "sinfo" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success

	# slurmd node in down state
	assert_line --regexp "juju-compute-[a-zA-Z ]+ up   infinite      1   down.*"
}

@test "test first node is down because it is new" {
	run juju run "sinfo -R" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success
	assert_output --partial "New node"
}

@test "assert that we can enlist that node and bring it to idle" {
	run juju run-action slurmd/leader -m $JUJU_MODEL node-configured --wait
	assert_success

	run juju run "sinfo" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success

	# check the node is not down anymore
	assert_line --regexp "juju-compute-[a-zA-Z ]+ up   infinite      1   idle.*"
}

@test "add a unit of slurmd and verify it is down" {
	myjuju add-unit slurmd -m $JUJU_MODEL

	run juju run "sinfo" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success

	# new node in down state
	assert_line --regexp "juju-compute-[a-zA-Z ]+ up   infinite      1   down.*"
	# old node should still be idle
	assert_line --regexp "juju-compute-[a-zA-Z ]+ up   infinite      1   idle.*"
}

@test "test if we have a new node" {
	run juju run "sinfo -R" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success
	assert_output --partial "New node"
}

@test "drain a node" {
	# drain slurmd/leaer
	host=$(juju run --model $JUJU_MODEL --unit slurmd/leader hostname)
	juju run-action -m $JUJU_MODEL slurmctld/leader drain nodename=$host reason="Unit test" --wait
	run juju run -m $JUJU_MODEL --unit slurmctld/leader "sinfo -R"
	assert_output --partial "Unit test"
}

@test "resume a drained node" {
	# resume slurmd
	host=$(juju run --model $JUJU_MODEL --unit slurmd/leader hostname)
	juju run-action -m $JUJU_MODEL slurmctld/leader drain nodename=$host reason="Unit test" --wait

	# resume it
	juju run-action -m $JUJU_MODEL slurmctld/leader resume nodename=$host --wait
	run juju run -m $JUJU_MODEL --unit slurmctld/leader "sinfo -n $host"

	assert_line --regexp "juju-compute-[a-zA-Z ]+ up   infinite      1   idle.*"
}
