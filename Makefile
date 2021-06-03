# Use bash shell in Make instead of sh
SHELL := /bin/bash
export PATH := /snap/bin:$(PATH)

# TARGETS
.PHONY: lint
lint: ## Run linter
	tox -e lint

.PHONY: version
version: ## Create/update version file
	@git describe --tags > version

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
	rm -rf *.charm
	rm -rf charm-slurm*/build
	rm -rf charm-slurm*/version
	rm -rf charm-slurm*/README.md

.PHONY: slurmd
slurmd: version ## Build slurmd
	@cp version LICENSE icon.svg charm-slurmd/
	@charmcraft pack --project-dir charm-slurmd

.PHONY: slurmctld
slurmctld: version ## pack slurmctld
	@cp version LICENSE icon.svg charm-slurmctld/
	@charmcraft pack --project-dir charm-slurmctld

.PHONY: slurmdbd
slurmdbd: version ## pack slurmdbd
	@cp version LICENSE icon.svg charm-slurmdbd/
	@charmcraft pack --project-dir charm-slurmdbd

.PHONY: slurmrestd
slurmrestd: version ## pack slurmrestd
	@cp version LICENSE icon.svg charm-slurmrestd/
	@charmcraft pack --project-dir charm-slurmrestd

.PHONY: charms
charms: readme slurmd slurmdbd slurmctld slurmrestd ## Build all charms

.PHONY: format
format: # reformat source python files
	isort charm-slurmd charm-slurmdbd charm-slurmctld --skip-glob '*/[0-9][0-9][0-9][0-9]*.py'
	black charm-slurmd charm-slurmdbd charm-slurmctld --exclude '\d{4}.*\.py'

# Display target comments in 'make help'
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# SETTINGS
# Use one shell for all commands in a target recipe
.ONESHELL:
# Set default goal
.DEFAULT_GOAL := help
