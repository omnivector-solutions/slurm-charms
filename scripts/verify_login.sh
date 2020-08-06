#!/bin/bash


set -e



juju ssh slurm-login/0 "/snap/bin/slurm.sinfo" > sinfo_out.txt
