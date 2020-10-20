export PATH := /snap/bin:$(PATH)

# TARGETS
lint: ## Run linter
	tox -e lint

clean: ## Remove .tox and build dirs
	rm -rf .tox/
	rm -rf venv/
	rm -rf *.charm

charms: ## Build all charms
	@charmcraft build --from charm-slurmd
	@charmcraft build --from charm-slurmctld
	@charmcraft build --from charm-slurmdbd
	@charmcraft build --from charm-slurmrestd
	@charmcraft build --from charm-slurm-configurator

pull-classic-snap: ## Pull the classic slurm snap from github
	@wget https://github.com/omnivector-solutions/snap-slurm/releases/download/20.02/slurm_20.02.1_amd64_classic.snap -O slurm.resource

pull-slurm-tar: ## Pull the slurm tar resource from s3
	@wget https://omnivector-public-assets.s3-us-west-2.amazonaws.com/resources/slurm-tar/20.02.3/slurm.tar.gz -O slurm.resource

push-charms-to-edge: ## Push charms to edge s3
	@./scripts/push_charms.sh edge

pull-charms-from-edge: clean ## pull charms from edge s3
	@./scripts/pull_charms.sh edge

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
