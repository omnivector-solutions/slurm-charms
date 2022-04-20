#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"


@test "test influxdb-info action work without relation" {
	run juju run-action --model $JUJU_MODEL slurmctld/leader influxdb-info --wait
	assert_output --regexp "influxdb: not related"
}

@test "test we can deploy influxdb and relate it to slurmctld" {
	run juju deploy --model $JUJU_MODEL influxdb

	juju wait-for application influxdb --query='status=="active"' --timeout=9m > /dev/null 2>&1
	myjuju relate slurmctld:influxdb-api influxdb:query

	run juju status --model $JUJU_MODEL --relations
	assert_output --regexp "slurmctld:influxdb-api"
	assert_output --regexp "influxdb:query"
}

@test "test influxdb-info action work after the relation" {
	run juju run-action --model $JUJU_MODEL slurmctld/leader influxdb-info --wait

	assert_output --regexp "database: osd-cluster"
	assert_output --regexp "ingress: [0-9]"
	assert_output --regexp "password: [a-zA-Z0-9]*"
	assert_output --regexp "port: \"8086\""
	assert_output --regexp "retention-policy: autogen"
	assert_output --regexp "user: slurm"
}

@test "test removing influxdb relation cleans up the relation data without breaking" {
	myjuju remove-relation slurmctld:influxdb-api influxdb:query
	juju wait-for unit slurmctld/0 --query='agent-status=="idle"'  --timeout=2m

	run juju run-action --model $JUJU_MODEL slurmctld/leader influxdb-info --wait
	assert_output --regexp "influxdb: not related"
}
