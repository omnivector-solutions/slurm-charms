export PATH := /snap/bin:$(PATH)

# TARGETS
.PHONY: lint
lint: ## Run linter
	tox -e lint

.PHONY: version
version: ## Create/update VERSION file
	@git describe --tags > VERSION

.PHONY: clean
clean: ## Remove .tox, build dirs, and charms
	rm -rf .tox/
	rm -rf venv/
	rm -rf *.charm
	rm -rf charm-slurm*/build
	rm -rf charm-slurm*/VERSION

.PHONY: slurmd
slurmd: version ## Build slurmd
	@cp VERSION charm-slurmd/
	@charmcraft pack --project-dir charm-slurmd

.PHONY: slurmctld
slurmctld: version ## pack slurmctld
	@cp VERSION charm-slurmctld/
	@charmcraft pack --project-dir charm-slurmctld

.PHONY: slurmdbd
slurmdbd: version ## pack slurmdbd
	@cp VERSION charm-slurmdbd/
	@charmcraft pack --project-dir charm-slurmdbd

.PHONY: slurmrestd
slurmrestd: version ## pack slurmrestd
	@cp VERSION charm-slurmrestd/
	@charmcraft pack --project-dir charm-slurmrestd

.PHONY: charms
charms: slurmd slurmdbd slurmctld slurmrestd ## Build all charms

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
# Use bash shell in Make instead of sh
SHELL := /bin/bash
