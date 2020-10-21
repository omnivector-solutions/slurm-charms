# charm-slurmctld
  
![alt text](.github/slurm.png)

<p align="center"><b>This is The Slurmctld charm for The Slurm Workload Manager</b>, <i>"The Slurm Workload Manager (formerly known as Simple Linux Utility for Resource Management or SLURM), or Slurm, is a free and open-source job scheduler for Linux and Unix-like kernels, used by many of the world's supercomputers and computer clusters."</i></p>

## Quickstart
```bash
juju deploy slurmctld
```

## Development
```bash
git clone git@github.com:omnivector-solutions/charm-slurmctld && cd charm-slurmctld
charmcraft build
juju deploy ./slurmctld.charm --resource slurm=/path/to/slurm.tar.gz
```
## Interfaces
- https://github.com/omnivector-solutions/interface-slurmd
- https://github.com/omnivector-solutions/ops-interface-slurmdbd

## Components
- https://github.com/omnivector-solutions/slurm-ops-manager
