#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"

myjuju () {
	juju "$@"
	juju-wait -t 540 -m $JUJU_MODEL
}

@test "test we can set a custom partition name" {
	partition="Unit-test-partition"
	myjuju config slurmd partition-name="$partition"

	run juju run --unit slurmctld/leader -m "$JUJU_MODEL" "sinfo"
	assert_output --partial "$partition "
}

@test "test we can set a default partition" {
	partition="Unit-test-partition"
	myjuju config slurmctld default-partition="$partition"

	run juju run --unit slurmctld/leader -m "$JUJU_MODEL" "sinfo"
	assert_output --partial "$partition* "
}
