#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"

myjuju () {
	juju "$@"
	juju-wait -t 540 -m "$JUJU_MODEL"
}


@test "test first node is down" {
	run juju run "sinfo" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success

	# slurmd node in down state
	assert_line --regexp "juju-compute-[a-zA-Z ]+up *infinite *1 *down.*"
}

@test "test first node is down because it is new" {
	run juju run "sinfo -R" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success
	assert_output --partial "New node"
}

@test "assert that we can enlist that node and bring it to idle" {
	run juju run-action slurmd/leader -m $JUJU_MODEL node-configured --wait
	assert_success

	# slurmctld needs some time to update its configs
	juju-wait -t 60 -m "$JUJU_MODEL"

	run juju run "sinfo" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success

	# check the node is not down anymore, therefore idle
	assert_line --partial "idle"
}

@test "add a unit of slurmd and verify it is down" {
	myjuju add-unit slurmd -m $JUJU_MODEL

	old_node=$(juju run --model $JUJU_MODEL --unit slurmd/leader hostname)

	# slurmctld needs some time to update its configs
	juju-wait -t 60 -m "$JUJU_MODEL"

	# attempt to give some time to juju and slurm to clam down
	flag="Polling sinfo 5 times"
	for i in {0..5}
	do
		sinfo_old=$(juju run "sinfo -n $old_node" -m $JUJU_MODEL --unit slurmctld/leader)
		sinfo=$(juju run "sinfo" -m $JUJU_MODEL --unit slurmctld/leader)
		if [[ "idle" == *"${sinfo_old}"* && "down" == *"${sinfo}"* ]]
		then
			flag="nodes are fine"
			break
		else
			sleep 1
		fi
	done

	# old node should still be idle
	run juju run "sinfo -n $old_node" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success
	assert_line --partial "idle"

	# new node in down state
	run juju run "sinfo" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success
	assert_line --partial "down"
}

@test "test if we have a new node" {
	run juju run "sinfo -R" -m $JUJU_MODEL --unit slurmctld/leader
	assert_success
	assert_output --partial "New node"
}

@test "test we can drain a node" {
	# drain slurmd/leader
	host=$(juju run --model $JUJU_MODEL --unit slurmd/leader hostname)
	juju run-action -m $JUJU_MODEL slurmctld/leader drain nodename=$host reason="Unit test" --wait

	run juju run -m $JUJU_MODEL --unit slurmctld/leader "sinfo -R"
	assert_output --partial "Unit test"
}

@test "test we can resume a drained node" {
	# slurmd/leader was drained, so resume it
	host=$(juju run --model $JUJU_MODEL --unit slurmd/leader hostname)
	juju run-action -m $JUJU_MODEL slurmctld/leader resume nodename=$host --wait

	run juju run -m $JUJU_MODEL --unit slurmctld/leader "sinfo -n $host"
	assert_line --partial "idle"
}

@test "Ping slurmrestd" {
	user="ubuntu"
	token=$(juju run --model "$JUJU_MODEL" --unit slurmctld/leader "scontrol token username=$user" | cut -d"=" -f 2)

	run juju run "curl --request GET localhost:6820/slurm/v0.0.36/ping \
	                   --location --silent --show-error \
	                   --header 'X-SLURM-USER-NAME: $user' \
	                   --header 'X-SLURM-USER-TOKEN: $token'" \
                     --unit slurmrestd/leader

	assert_output --partial "\"ping\": \"UP\","
}
