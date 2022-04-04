#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"


@test "Querying the default package names" {
	run juju run-action -m "$JUJU_MODEL" slurmd/leader nvidia-package --wait
	assert_output --regexp "nvidia-package: (nvidia-driver-latest-dkms|cuda-drivers)"
}

@test "Changing the default package name" {
	run juju run-action -m "$JUJU_MODEL" slurmd/leader nvidia-package package=fooo --wait
	assert_output --regexp "nvidia-package: fooo"
}

@test "Resetting the default package name" {
	run juju run-action -m "$JUJU_MODEL" slurmd/leader nvidia-package package="" --wait
	assert_output --regexp "nvidia-package: (nvidia-driver-latest-dkms|cuda-drivers)"
}

@test "Querying the default repos" {
	run juju run-action -m "$JUJU_MODEL" slurmd/leader nvidia-repo --wait

	# should not be set
	assert_output --partial "nvidia-repo: \"\""
}
