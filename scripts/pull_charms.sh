#!/bin/bash

set -e

stage=$1

for charm in slurmctld slurmd slurmdbd slurmrestd; do
    charm_loc="https://omnivector-public-assets.s3-us-west-2.amazonaws.com/charms/$charm/$stage/$charm.charm"
    echo "Copying $charm_loc to $charm.charm"
    wget $charm_loc
done
