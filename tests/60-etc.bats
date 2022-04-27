#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"

# etcd host and port
host=$(juju run --unit slurmctld/leader "unit-get public-address")
port=2379

# user/pass for querying munge key
user="fooooooooo"
pass="1234abcdef"

# helper to get the etcd auth token
function get_token()
{
	local user=$1
	local pass=$2
	local url="$host:$port/v3/auth/authenticate"

	local token=$(curl -L -s -X POST "$url" -d '{"name":"'"$user"'", "password":"'"$pass"'"}' | jq .token)

	echo ${token//\"/} # remove quotes
}


@test "Assert etcd is up" {
	run curl -X POST "$host:$port/v3/maintenance/status"
	assert_output --regexp '"version":"3.5.0"'
}

@test "Assert we can get the root password" {
	run juju run-action -m "$JUJU_MODEL" slurmctld/leader etcd-get-root-password --wait

	assert_output --regexp "username: root"
	assert_output --regexp "password: [a-zA-Z0-9]{20}"
}

@test "Assert we can get the nodelist" {
	local password=$(juju run-action slurmctld/leader etcd-get-slurmd-password --wait --format=json | jq .[].results.password )
	local key=$(printf nodes/all_nodes | base64)
	local token=$(get_token "slurmd" ${password//\"/})

	run curl -X POST "$host:$port/v3/kv/range" -d '{"key":"'$key'"}' -H "Authorization: ${token}"

	assert_output --regexp "\"key\":\"$key"
}

@test "Assert we can't get the munge key without authentication" {
	local key=$(printf munge/key | base64)
	run curl -X POST -D - "$host:$port/v3/kv/range" -d '{"key":"'$key'"}'

	assert_output --partial "400 Bad Request"
	assert_output --partial "etcdserver: user name is empty"
}

@test "Assert wrong user can't get the munge key" {
	local password=$(juju run-action slurmctld/leader etcd-get-slurmd-password --wait --format=json | jq .[].results.password )
	local key=$(printf munge/key | base64)
	local token=$(get_token "slurmd" ${password//\"/})

	run curl -L -s -X POST "$host:$port/v3/kv/range" -H "Authorization: ${token}" -d '{"key":"'$key'"}'
	assert_output --partial "etcdserver: permission denied"
}

@test "Assert we can create an user to query etcd" {
	run juju run-action slurmctld/leader -m $JUJU_MODEL etcd-create-munge-account user="$user" password="$pass" --wait
	assert_output --partial "created-new-user: $user"
}

@test "Assert we can get the munge key with authentication" {
	local key=$(printf munge/key | base64)
	local token=$(get_token "$user" "$pass")

	run curl -L -s -X POST "$host:$port/v3/kv/range" -H "Authorization: ${token}" -d '{"key":"'$key'"}'

	assert_output --regexp "\"key\":\"$key"
}
