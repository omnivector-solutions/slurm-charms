# charm-slurmd

![alt text](.github/slurm.png)

<p align="center"><b>This is the Slurmd charm for the Slurm Workload Manager</b>, <i>"The Slurm Workload Manager (formerly known as Simple Linux Utility for Resource Management or SLURM), or Slurm, is a free and open-source job scheduler for Linux and Unix-like kernels, used by many of the world's supercomputers and computer clusters."</i></p>

Requirements
------------
- Ubuntu 20.04
- juju 2.8.1
- charmcraft

Quickstart
----------
```bash
juju deploy slurmd
```

## Development
```bash
git clone git@github.com:omnivector-solutions/charm-slurmd && cd charm-slurmd
charmcraft build
juju deploy ./slurmd.charm --resource slurm=/path/to/slurm.tar.gz
```



Interfaces
----------
- https://github.com/omnivector-solutions/interface-slurmd

Components
----------
- https://github.com/omnivector-solutions/slurm-ops-manager

Contact
-------
 - Author: OmniVector Solutions 
 - Bug Tracker: [here](https://github.com/omnivector-solutions/charm-slurmdbd)
