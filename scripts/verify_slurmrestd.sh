#!/bin/bash
# Generate a jwt token, find slurmrestd ip, use the token to make a request to slurmrestd api.
# Exit 0 if slurmrestd api returns a 200, -1 if anything else.

set -e

token=$($(which python3) -c "import jwt; print(jwt.encode({'some': 'payload'}, 'secret', algorithm='HS256').decode())")
slurmrestd_ip=$(juju status --format json | jq -r '.applications["slurmrestd"].units[]["public-address"]')
slurmrestd_api_status_code=$(curl -H "X-SLURM-USER-NAME: ubuntu" \
                                  -H "X-SLURM-USER-TOKEN: $token" \
                                  -s -o /dev/null -w "%{http_code}" \
                                  "http://$slurmrestd_ip:6820/openapi/v3")

if [[ $slurmrestd_api_status_code == "200" ]]; then
	exit 0
else
	exit -1
