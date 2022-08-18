#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"


@test "test singularity is installed" {
	run juju run-action -m "$JUJU_MODEL" slurmd/leader singularity-install --wait
	run juju run --unit slurmd/leader --model "$JUJU_MODEL" "singularity --version"
	assert_output --partial "singularity-ce version "
}