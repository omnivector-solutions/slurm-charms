# Slurm Charms
This is the home of the slurm charms.

## Deployment
The `make deploy-*` commands included in the makefile can be used to deploy the bundles contained in the `bundles/` directory. 

## Build
To build all of the slurm charms, from the root of this project run, `make charms`.
The successfull execution of this command will produce built `.charm` files for each charm contained in this repo, and place them in the `out/` directory.
```bash
$ make charms
```
## Slurm Configuration

To deploy slurm with multiple partions you need to set the partition config value for the slurmd node on deployment.

```bash
juju deploy ./slurmd.charm p1 --config partion-name="partition1"
juju deploy ./slurmd.charm p2 --config partion-name="partiotion2"
```
This will deploy 2 units, p1 and p2, both of which are in a seperate partition.

To specify cluster name:
```bash
juju deploy ./slurm-configurator.charm --config cluster_name="mycluster"
```

#### Copyright
* OmniVector Solutions <admin@omnivector.solutions>
