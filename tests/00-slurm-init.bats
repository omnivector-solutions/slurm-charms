#!/bin/npx bats

load "../node_modules/bats-support/load.bash"
load "../node_modules/bats-assert/load.bash"

myjuju () {
	juju "$@"
	juju-wait -t 540 -m $JUJU_MODEL
}


@test "test first node is down" {
	run juju run "sinfo" -m $JUJU_MODEL --unit slurm-configurator/leader
	assert_success

	# slurmd node in down state
	assert_line --regexp "juju-compute-[a-zA-Z ]+ up   infinite      1   down.*"
	# slurm configurator should be exactly like this
	assert_line --partial "configurator*     inact   infinite      1   idle"
}

@test "test first node is down because it is new" {
	run juju run "sinfo -R" -m $JUJU_MODEL --unit slurm-configurator/leader
	assert_success
	assert_output --partial "New node"
}

@test "assert that we can enlist that node" {
	run juju run-action slurmd/leader -m $JUJU_MODEL node-configured
	assert_success
}

@test "assert that we can enlist that node and bring it to live" {
	# wait for the node to be up
	sleep 15

	run juju run "sinfo" -m $JUJU_MODEL --unit slurm-configurator/leader
	assert_success

	# check the node is not down anymore
	# due to THE BUG in the configuration regeneration, sometimes this test
	# fails. This should be fixed in the future
	assert_line --regexp "juju-compute-[a-zA-Z ]+ up   infinite      1   .*" # FIXME

	# slurm configurator should still be working
	assert_line --partial "configurator*     inact   infinite      1   idle"
}

@test "add a unit of slurmd and verify it is down" {
	myjuju add-unit slurmd -m $JUJU_MODEL

	run juju run "sinfo" -m $JUJU_MODEL --unit slurm-configurator/leader
	assert_success

	# new node in down state
	assert_line --regexp "juju-compute-[a-zA-Z ]+ up   infinite      .   down.*" # FIXME
	# old node should still be idle
	#assert_line --regexp "juju-compute-[a-zA-Z ]+ up   infinite      1   idle.*" # FIXME
	# slurm configurator should not have changed
	assert_line --partial "configurator*     inact   infinite      1   idle"
}

@test "test if we have a new node" {
	run juju run "sinfo -R" -m $JUJU_MODEL --unit slurm-configurator/leader
	assert_success
	assert_output --partial "New node"
}
