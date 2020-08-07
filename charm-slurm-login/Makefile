# TARGETS
lint: ## Run linter
	tox -e lint

clean: ## Remove .tox and build dirs
	rm -rf .tox/
	rm -rf venv/
venv:
	@mkdir -p venv
	@pip3 install -U --target=./venv --requirement=./requirements.txt

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
