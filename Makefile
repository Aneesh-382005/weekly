.PHONY: help build list test clean

help:  ## show this help
	@grep -E '^[a-z]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-8s %s\n", $$1, $$2}'

build: ## generate calendar.ics from the schedule YAML
	PYTHONPATH=. python3 -m weekly.cli build -o calendar.ics

list: ## print every occurrence to the terminal
	PYTHONPATH=. python3 -m weekly.cli list

test: ## run the test suite
	PYTHONPATH=. python3 -m pytest -q

clean: ## remove generated files
	rm -f calendar.ics
	rm -rf __pycache__ */__pycache__ .pytest_cache *.egg-info
