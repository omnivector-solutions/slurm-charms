#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"


@test "Assert we can update nhc.conf" {
	myjuju config slurmd nhc-conf="# new config"
	sleep 5 # just to be sure all units updated correctly

	run juju run-action -m "$JUJU_MODEL" slurmd/leader show-nhc-config --wait
	assert_output --partial "# new config"
}

@test "Assert we can change the slurm settings for NHC - interval" {
	myjuju config slurmctld health-check-interval=3
	run juju run-action -m "$JUJU_MODEL" slurmctld/leader show-current-config --wait
	assert_output --partial "HealthCheckInterval=3"
}

@test "Assert we can change the slurm settings for NHC - state" {
	myjuju config slurmctld health-check-state="CYCLE,ANY"
	run juju run-action -m "$JUJU_MODEL" slurmctld/leader show-current-config --wait
	assert_output --partial "HealthCheckNodeState=CYCLE,ANY"
}

@test "Assert we can change the slurm settings for NHC - params" {
	run juju run -m "$JUJU_MODEL" --unit slurmd/leader cat /usr/sbin/omni-nhc-wrapper
	assert_output --partial "/usr/sbin/nhc-wrapper #"

	local params="-M admin@omnivector.solutions -S notifications"
	myjuju config slurmctld health-check-params="$params"
	juju wait-for unit slurmctld/0 --query='agent-status=="idle"'

	run juju run -m "$JUJU_MODEL" --unit slurmd/leader cat /usr/sbin/omni-nhc-wrapper
	assert_output --partial "/usr/sbin/nhc-wrapper $params"
}
