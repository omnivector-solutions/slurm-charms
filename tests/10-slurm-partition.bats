#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"


@test "test we can set a custom partition name" {
	partition="Unit-test-partition"
	myjuju config --model $JUJU_MODEL slurmd partition-name="$partition"

	run juju run --unit slurmctld/leader --model "$JUJU_MODEL" "sinfo"
	assert_output --partial "$partition "
}

@test "test partition name does not have spaces" {
	partition="There are spaces here"
	myjuju config --model $JUJU_MODEL slurmd partition-name="$partition"

	run juju run --unit slurmctld/leader --model "$JUJU_MODEL" "sinfo"
	refute_output --partial "$partition "
	assert_output --partial "${partition// /-} "
}

@test "test we can set a default partition" {
	partition="Default-test-partition"
	myjuju config --model $JUJU_MODEL slurmd partition-name="$partition"
	myjuju config --model $JUJU_MODEL slurmctld default-partition="$partition"
	juju wait-for application slurmctld --query='status=="active"' --timeout=1m > /dev/null 2>&1

	run juju run --unit slurmctld/leader --model "$JUJU_MODEL" "sinfo"
	assert_output --partial "$partition* "
}
