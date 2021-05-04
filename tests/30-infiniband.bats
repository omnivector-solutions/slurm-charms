#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"


myjuju () {
	juju "$@"
	juju-wait -t 540 -m $JUJU_MODEL
}

@test "Check default repo is not set" {
	run juju run-action slurmd/leader get-infiniband-repo --wait
	assert_output --partial "Repository not set up"
}

@test "Set default repo" {
	juju run-action slurmd/leader set-infiniband-repo repo="" --wait

	run juju run-action slurmd/leader get-infiniband-repo --wait
	assert_output --partial "mellanox.com/public/repo/mlnx_ofed/"
}

@test "Test changing the repo" {
	repo=$(echo [new custom repo] | base64)
	juju run-action slurmd/leader set-infiniband-repo repo="$repo" --wait

	run juju run-action slurmd/leader get-infiniband-repo --wait
	assert_output --partial "new custom repo"
}

@test "Reset custom repo to default" {
	juju run-action slurmd/leader set-infiniband-repo repo="" --wait

	run juju run-action slurmd/leader get-infiniband-repo --wait
	assert_output --partial "mellanox.com/public/repo/mlnx_ofed/"
}
