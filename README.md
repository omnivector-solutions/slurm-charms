# Slurm Charms
This is the home of the slurm charms.

## Deployment

## Build
To build all of the slurm charms, from the root of this project run, `make charms`.
The successfull execution of this command will produce built `.charm` files for each charm contained in this repo, and place them in the `out/` directory.
```bash
$ make charms
```
```bash
$ ls -lah *.charm
-rw-rw-r-- 1 bdx bdx 581K Aug  3 15:22 slurmctld.charm
-rw-rw-r-- 1 bdx bdx 584K Aug  3 15:22 slurmdbd.charm
-rw-rw-r-- 1 bdx bdx 580K Aug  3 15:22 slurmd.charm
```

#### Copyright
* OmniVector Solutions <admin@omnivector.solutions>
