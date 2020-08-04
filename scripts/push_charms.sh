#!/bin/bash

set -e

stage=$1

for charm in slurmctld slurmd slurmdbd; do
    s3_loc="s3://omnivector-public-assets/charms/$charm/$stage/"
    echo "Copying $charm.charm to $s3$charm.charm"
    aws s3 cp $charm.charm $s3_loc --recursive --acl public-read
done
