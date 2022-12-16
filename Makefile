# Use bash shell in Make instead of sh
SHELL := /bin/bash
export PATH := /snap/bin:$(PATH)

ifeq ($(VERBOSE), 1)
	VERBOSE="--verbose"
endif

# TARGETS
.PHONY: lint
lint: ## Run linter
	tox -e lint

.PHONY: version
version: ## Create/update version file
	@git describe --tags --dirty --always > version

.PHONY: readme
readme: ## create charms' README.md
	@for charm in slurmd slurmdbd slurmctld slurmrestd; do \
		cp README.md charm-$${charm}/README.md ;\
		sed -i -e "s|Welcome to the Omnivector Slurm Distribution!|$${charm} charm|g" charm-$${charm}/README.md
	done

.PHONY: clean
clean: ## Remove .tox, build dirs, and charms
	rm -rf .tox/
	rm -rf venv/
	rm -rf node_modules/
	find . -name "*.charm" -delete
	rm -rf charm-slurm*/build
	rm -rf charm-slurm*/version
	rm -rf charm-slurm*/README.md

.PHONY: deepclean
deepclean: clean ## Cleanup charmcraft/lxd
	@charmcraft clean --project-dir charm-slurmctld
	@charmcraft clean --project-dir charm-slurmd
	@charmcraft clean --project-dir charm-slurmdbd
	@charmcraft clean --project-dir charm-slurmrestd

.PHONY: slurmd
slurmd: version ## Build slurmd
	@cp version LICENSE icon.svg charm-slurmd/
	@charmcraft pack --project-dir charm-slurmd ${VERBOSE}
	@mv slurmd_ubuntu-20.04-amd64_ubuntu-22.04-amd64_centos-7-amd64.charm slurmd.charm

.PHONY: slurmctld
slurmctld: version ## pack slurmctld
	@cp version LICENSE icon.svg charm-slurmctld/
	@charmcraft pack --project-dir charm-slurmctld ${VERBOSE}
	@mv slurmctld_ubuntu-20.04-amd64_ubuntu-22.04-amd64_centos-7-amd64.charm slurmctld.charm

.PHONY: slurmdbd
slurmdbd: version ## pack slurmdbd
	@cp version LICENSE icon.svg charm-slurmdbd/
	@charmcraft pack --project-dir charm-slurmdbd ${VERBOSE}
	@mv slurmdbd_ubuntu-20.04-amd64_ubuntu-22.04-amd64_centos-7-amd64.charm slurmdbd.charm

.PHONY: slurmrestd
slurmrestd: version ## pack slurmrestd
	@cp version LICENSE icon.svg charm-slurmrestd/
	@charmcraft pack --project-dir charm-slurmrestd ${VERBOSE}
	@mv slurmrestd_ubuntu-20.04-amd64_ubuntu-22.04-amd64_centos-7-amd64.charm slurmrestd.charm

.PHONY: charms
charms: readme slurmd slurmdbd slurmctld slurmrestd ## Build all charms

.PHONY: tests-centos
tests-centos: clean charms ## Run bats tests on centos
	./run_tests centos

.PHONY: tests-focal
tests-focal: clean charms ## Run bats tests on ubuntu focal
	./run_tests focal

.PHONY: tests
tests: tests-centos tests-focal ## Run bats tests

# Display target comments in 'make help'
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# SETTINGS
# Use one shell for all commands in a target recipe
.ONESHELL:
# Set default goal
.DEFAULT_GOAL := help
