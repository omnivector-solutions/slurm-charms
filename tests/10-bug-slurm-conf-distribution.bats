#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"


myjuju () {
	juju "$@"
	juju-wait -t 540 -m $JUJU_MODEL
}


@test "Assert we can rebuild slurm.conf correctly" {
	SLURM_CONF="/etc/slurm/slurm.conf"

	# manually modify slurm.conf in units
	for unit in slurm-configurator slurmctld slurmd
	do
		juju run --unit ${unit}/leader "sudo echo \## BUG $unit >> $SLURM_CONF"
	done

	# run the reconfigure-slurm action in slurm-configurator
	myjuju run-action slurm-configurator/leader reconfigure-slurm --wait
	# not sure what's the best way to wait for an action to complete
	sleep 15

	# tail the slurm conf and check if there's no ## BUG
	for unit in slurm-configurator slurmctld slurmd
	do
		run juju run --unit ${unit}/leader "tail -n 2 $SLURM_CONF"
		refute_output --partial '## BUG'
	done
}

