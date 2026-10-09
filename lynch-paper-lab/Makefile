.PHONY: test lock-config
test:
	PYTHONPATH=src python3 -m unittest discover -s tests -t . -v
lock-config:
	PYTHONPATH=src python3 -m lpl.config --write-lock config/strategy_baseline.v1.toml
