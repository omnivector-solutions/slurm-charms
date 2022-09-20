#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"


@test "test MPI is installed" {
	run juju run-action -m "$JUJU_MODEL" slurmd/leader mpi-install --wait
	run juju run --unit slurmd/leader --model "$JUJU_MODEL" "mpirun --version"
	assert_output --partial "HYDRA build "
}