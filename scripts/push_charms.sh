#!/bin/bash

set -e

stage=$1

for charm in slurmctld slurmd slurmdbd; do
    s3="s3://omnivector-charms/$charm/$stage/"
    echo "Copying $charm.charm to $s3$charm.charm"
    aws s3 cp $charm.charm $s3
done
