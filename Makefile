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
	@charmcraft build --from charm-slurm-login

pull-classic-snap: ## Pull the classic slurm snap from github
	@wget https://github.com/omnivector-solutions/snap-slurm/releases/download/20.02/slurm_20.02.1_amd64_classic.snap -O slurm.resource

pull-slurm-tar: ## Pull the slurm tar resource from s3
	@wget https://omnivector-public-assets.s3-us-west-2.amazonaws.com/resources/slurm-tar/20.02.3/slurm.tar.gz -O slurm.resource

push-charms-to-edge: ## Push charms to edge s3
	@./scripts/push_charms.sh edge

pull-charms-from-edge: clean ## pull charms from edge s3
	@./scripts/pull_charms.sh edge


deploy-focal-bundle-on-aws-from-edge-with-snap: pull-classic-snap pull-charms-from-edge ## Deploy focal aws bundle using the slurm snap and edge charms
	@juju deploy ./bundles/slurm-core-focal-aws/bundle.yaml

deploy-focal-bundle-on-aws-from-edge-with-tar: pull-slurm-tar pull-charms-from-edge ## Deploy focal aws bundle using the slurm tar and edge charms
	@juju deploy ./bundles/slurm-core-focal-aws/bundle.yaml


deploy-focal-bundle-on-lxd-from-edge-with-snap: pull-classic-snap pull-charms-from-edge ## Deploy focal lxd bundle using the slurm snap and edge charms
	@juju deploy ./bundles/slurm-core-focal-lxd/bundle.yaml

deploy-focal-bundle-on-lxd-from-edge-with-tar: pull-slurm-tar pull-charms-from-edge ## Deploy focal lxd bundle using localally built charms and snap
	@juju deploy ./bundles/slurm-core-focal-lxd/bundle.yaml


deploy-focal-bundle-on-lxd-from-local-with-snap: ## Deploy focal lxd bundle using localally built charms and snap
	@if ! [[ -f slurm.resource ]]; then\
	    wget https://github.com/omnivector-solutions/snap-slurm/releases/download/20.02/slurm_20.02.1_amd64_classic.snap -O slurm.resource;\
	fi
	@juju deploy ./bundles/slurm-core-focal-lxd/bundle.yaml

deploy-focal-bundle-on-lxd-from-local-with-tar: pull-slurm-tar ## Deploy focal lxd bundle using localally built charms and slurm.tar.gz
	@juju deploy ./bundles/slurm-core-focal-lxd/bundle.yaml


deploy-bionic-bundle-on-lxd-from-local-with-snap: ## Deploy focal lxd bundle using localally built charms and snap
	@if ! [[ -f slurm.resource ]]; then\
	    wget https://github.com/omnivector-solutions/snap-slurm/releases/download/20.02/slurm_20.02.1_amd64_classic.snap -O slurm.resource;\
	fi
	@juju deploy ./bundles/slurm-core-bionic-lxd/bundle.yaml

deploy-bionic-bundle-on-lxd-from-local-with-tar: pull-slurm-tar ## Deploy focal lxd bundle using localally built charms and slurm.tar.gz
	@juju deploy ./bundles/slurm-core-bionic-lxd/bundle.yaml


deploy-centos7-bundle-on-aws-from-local-with-snap: ## Deploy centos7 aws bundle using locally built charm and snap
	@if ! [[ -f slurm.resource ]]; then\
	    wget https://github.com/omnivector-solutions/snap-slurm/releases/download/20.02/slurm_20.02.1_amd64_classic.snap -O slurm.resource;\
	fi
	@juju deploy ./bundles/slurm-core-centos7-aws/bundle.yaml

deploy-centos7-bundle-on-aws-from-edge-with-snap: pull-classic-snap pull-charms-from-edge ## Deploy centos7 aws bundle using edge charms and snap
	@juju deploy ./bundles/slurm-core-centos7-aws/bundle.yaml

deploy-centos7-bundle-on-aws-from-edge-with-tar: pull-slurm-tar pull-charms-from-edge ## Deploy centos7 aws bundle using edge charms and tar
	@juju deploy ./bundles/slurm-core-centos7-aws/bundle.yaml


grab-slurm-logs: # Use juju scp to get the logs from slurm application units in the model
	@scripts/grab_logs_from_slurm_units.sh


test-slurmrestd-api-returns-200: # Requst slurmrestd api endpoint to verify operational status
	@scripts/verify_slurmrestd.sh

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
