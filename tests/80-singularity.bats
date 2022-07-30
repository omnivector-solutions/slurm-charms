#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"


@test "test singularity is installed" {
	partition="Unit-test-partition"
	myjuju config --model $JUJU_MODEL slurmd partition-name="$partition"

	run juju run --unit slurmd/0 --model "$JUJU_MODEL" "singularity --version"
	assert_output --partial "singularity-ce version "
}