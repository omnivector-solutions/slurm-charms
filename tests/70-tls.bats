#!/bin/npx bats

load "../node_modules/bats-support/load"
load "../node_modules/bats-assert/load"
. "tests/utils.sh"

# etcd host and port
host=$(juju run --unit slurmctld/leader "unit-get public-address")
port=2379

CANAME=Omni-RootCA
MYCERT=etcd


# generate certs
function create_certs()
{
	# create the CA
	openssl genrsa -aes256 -passout pass:1234 -out $CANAME.key 4096
	openssl req -x509 -new -nodes -passin pass:1234 -key $CANAME.key \
	            -sha256 -days 1826 -out $CANAME.crt \
	            -subj '/CN=Omni-RootCA/OU=Omni'

	# create the server certs
	openssl req -new -nodes -out $MYCERT.csr -newkey rsa:4096 \
	            -keyout $MYCERT.key -subj '/O=Omnietcd/CN=HPC'

	local slurmctld_hostname=$(juju run --unit slurmctld/leader "hostname")
	cat > $MYCERT.v3.ext << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
DNS.2 = $slurmctld_hostname
IP.1 = 127.0.0.1
IP.2 = $host
EOF

	openssl x509 -req -passin pass:1234 -in $MYCERT.csr -CA $CANAME.crt \
	             -CAkey $CANAME.key -CAcreateserial -out $MYCERT.crt \
	             -days 730 -sha256 -extfile $MYCERT.v3.ext
}


@test "Assert we can setup TLS" {
	create_certs

	juju config --model "$JUJU_MODEL" slurmctld tls-cert="$(cat etcd.crt)"
	juju config --model "$JUJU_MODEL" slurmctld tls-key="$(cat etcd.key)"
	juju config --model "$JUJU_MODEL" slurmctld tls-ca-cert="$(cat Omni-RootCA.crt)"

	sleep 5
	juju wait-for unit slurmctld/0 --query='agent-status=="idle"' --timeout=9m

	# etcd should still be up
	run curl -s -X POST "https://$host:$port/v3/maintenance/status" --cacert etcd.crt
	assert_output --regexp '"version":"3.5.0"'
}

@test "Assert we can get the nodelist with TLS cert" {
	local password=$(juju run-action slurmctld/leader etcd-get-slurmd-password --wait --format=json | jq .[].results.password)
	local key=$(printf nodes/all_nodes | base64)

	local url="https://$host:$port/v3/auth/authenticate"
	local token=$(curl -L -s -X POST "$url" -d '{"name":"slurmd", "password":"'"${password//\"/}"'"}' --cacert etcd.crt | jq .token)

	run curl -X POST "https://$host:$port/v3/kv/range" -d '{"key":"'$key'"}' -H "Authorization: ${token//\"/}" --cacert etcd.crt
	assert_output --regexp "\"key\":\"$key"
}


@test "Assert we can remove TLS certs" {
	juju config --model "$JUJU_MODEL" slurmctld tls-cert=""
	juju config --model "$JUJU_MODEL" slurmctld tls-key=""
	juju config --model "$JUJU_MODEL" slurmctld tls-ca-cert=""

	sleep 5
	juju wait-for unit slurmctld/0 --query='agent-status=="idle"' --timeout=9m

	# etcd should still be up
	run curl -X POST "http://$host:$port/v3/maintenance/status"
	assert_output --regexp '"version":"3.5.0"'
}
