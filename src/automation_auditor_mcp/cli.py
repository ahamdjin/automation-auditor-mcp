"""Development-only CLI; explicitly read paths chosen by the local operator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from .core import audit_workflow, supported_platforms


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only multi-platform automation auditor")
    parser.add_argument("file", nargs="?", help="Path to a local export or Trigger.dev source")
    parser.add_argument("--platform", default="auto", help="n8n, dify, trigger, activepieces, auto")
    parser.add_argument("--list-platforms", action="store_true")
    args = parser.parse_args()
    if args.list_platforms:
        print(json.dumps(supported_platforms(), indent=2))
        return 0
    if not args.file:
        parser.error("Specify a local file or --list-platforms")
    path = Path(args.file).resolve()
    if not path.is_file() or path.stat().st_size > 1_000_000:
        parser.error("Input must be an existing file below 1 MB")
    source = path.read_text(encoding="utf-8")
    result = audit_workflow(args.platform, source)
    print(json.dumps(result, indent=2))
    return 2 if not result["supported"] else (
        1 if result["summary"]["errors"] else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
