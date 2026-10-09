"""Load the strategy config and verify it against its committed hash.

The hash is over a canonical JSON form (parsed TOML, sorted keys), so comments and
whitespace do not count as rule changes but any value change does.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path


class ConfigIntegrityError(RuntimeError):
    pass


class ConfigNotFrozenError(RuntimeError):
    pass


def canonical_hash(config: dict) -> str:
    blob = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()


def lock_path(config_path: Path) -> Path:
    return config_path.with_suffix(".sha256")


def load_config(config_path: Path, require_frozen: bool = True) -> tuple[dict, str]:
    config_path = Path(config_path)
    with config_path.open("rb") as f:
        config = tomllib.load(f)
    actual = canonical_hash(config)
    expected = lock_path(config_path).read_text().split()[0]
    if actual != expected:
        raise ConfigIntegrityError(
            f"{config_path.name}: hash {actual} does not match lock {expected}. "
            "Frozen rules were changed; create a new version instead."
        )
    if require_frozen and config["meta"]["status"] != "FROZEN":
        raise ConfigNotFrozenError(
            f"{config_path.name} status is {config['meta']['status']!r}; owner approval required."
        )
    return config, actual


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("config")
    p.add_argument("--write-lock", action="store_true")
    args = p.parse_args(argv)
    path = Path(args.config)
    with path.open("rb") as f:
        digest = canonical_hash(tomllib.load(f))
    if args.write_lock:
        lock_path(path).write_text(f"{digest}  {path.name}\n")
    print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
