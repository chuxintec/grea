"""Inspect local GREA feature availability without installing or running game code."""
import argparse
import json
from importlib.util import find_spec
from pathlib import Path

from grea.common import write_new


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New receipt directory")
    return parser


def main(argv=None):
    output = build_parser().parse_args(argv).output
    output.mkdir()
    features = {name: find_spec(f"grea.{package}.cli") is not None
                for name, package in (("recover", "recovery"), ("develop", "development"))}
    ready = all(features.values())
    result = dict(status="ok" if ready else "needs_action", ready=ready, features=features,
                  required_providers=[], native="not_run", gameplay="not_run")
    write_new(output / "result.json", result)
    print(json.dumps(result))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
