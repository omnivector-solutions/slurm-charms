#!/bin/bash

set -eux


for charm in slurmd slurmctld slurmdbd; do
    dir=charm-$charm
    /snap/bin/charmcraft build --from $dir/
done
