# charm-slurmdbd
  
![alt text](.github/slurm.png)

<p align="center"><b>This is the Slurmdbd charm for the Slurm Workload Manager</b>, <i>"The Slurm Workload Manager (formerly known as Simple Linux Utility for Resource Management or SLURM), or Slurm, is a free and open-source job scheduler for Linux and Unix-like kernels, used by many of the world's supercomputers and computer clusters."</i></p>

## Quickstart
```bash
juju deploy slurmdbd
```

## Development
```bash
git clone git@github.com:omnivector-solutions/charm-slurmdbd && cd charm-slurmdbd
charmcraft build
juju deploy ./slurmdbd.charm --resource slurm=/path/to/slurm.{tar.gz|snap}
```
## Interfaces
- https://github.com/omnivector-solutions/operator-interface-slurmdbd
- https://github.com/omnivector-solutions/operator-interface-mysql

## Components
- https://github.com/omnivector-solutions/slurm-ops-manager
