# Slurm Charms
This is the home of the slurm charms.


## Build
To build all of the slurm charms, from the root of this project run, `make charms`.
The successfull execution of this command will produce built `.charm` files for each charm contained in this repo, and place them in the `out/` directory.
```bash
$ make charms
```
```bash
$ ls -lah out/
total 96M
drwxrwxr-x 2 bdx bdx 4.0K Jul 30 02:38 .
drwxrwxr-x 9 bdx bdx 4.0K Jul 30 02:38 ..
-rw-rw-r-- 1 bdx bdx  32M Jul 30 02:38 slurmctld.charm
-rw-rw-r-- 1 bdx bdx  32M Jul 30 02:38 slurmdbd.charm
-rw-rw-r-- 1 bdx bdx  32M Jul 30 02:38 slurmd.charm
```

What is happening behind the scenes you ask?

The build scripts generate a python environment using the manylinux docker image and distribute that virtualenv
to the charms prior to building the charms themselves.

#### Copyright
* OmniVector Solutions <admin@omnivector.solutions>
