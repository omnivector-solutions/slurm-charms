#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"


myjuju () {
	juju "$@"
	juju-wait -t 540 -m $JUJU_MODEL
}


@test "Assert we can update nhc.conf" {
	nhc_conf="/etc/nhc/nhc.conf"

	juju config slurmd nhc-conf="# new config"
	sleep 5 # just to be sure all units updated correctly

	run juju run --unit slurmd/leader "tail -n 4 $nhc_conf"
	assert_output --partial "# new config"
}

@test "Assert we can change the slurm settings for NHC - interval" {
	juju config slurmctld health-check-interval=3
	run juju run-action slurmctld/leader show-current-config --wait
	assert_output --partial "HealthCheckInterval=3"
}

@test "Assert we can change the slurm settings for NHC - state" {
	juju config slurmctld health-check-state="CYCLE,ANY"
	run juju run-action slurmctld/leader show-current-config --wait
	assert_output --partial "HealthCheckNodeState=CYCLE,ANY"
}
