#!/bin/bash

set -e


export PATH=$PATH:/snap/bin



slurm_units=$(juju status slurmrestd slurmdbd slurmd slurmctld --format json | jq -r '.applications | map_values(.units) | .[] | keys | .[]')

for slurm_unit in $slurm_units; do
    juju scp $slurm_unit:/var/log/juju/unit-*.log .
done
