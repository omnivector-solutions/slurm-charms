export PATH := /snap/bin:$(PATH)

# TARGETS
lint: ## Run linter
	tox -e lint

clean: ## Remove .tox and build dirs
	rm -rf .tox/
	rm -rf venv/

charms:
	@charmcraft build --from charm-slurmd
	@charmcraft build --from charm-slurmctld
	@charmcraft build --from charm-slurmdbd

pull-classic-snap:
	@wget https://github.com/omnivector-solutions/snap-slurm/releases/download/20.02/slurm_20.02.1_amd64_classic.snap -O slurm_snap.resource

pull-slurm-tar-resource-from-s3:
	@aws s3 cp s3://omnivector-slurm-resoruces/slurm-tar/20.02.3/slurm.tar.gz slurm_tar.resource

push-charms-to-edge:
	@./scripts/push_charms.sh edge

# Display target comments in 'make help'
help: 
	grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# SETTINGS
# Use one shell for all commands in a target recipe
.ONESHELL:
# Set default goal
.DEFAULT_GOAL := help
# Use bash shell in Make instead of sh 
SHELL := /bin/bash
