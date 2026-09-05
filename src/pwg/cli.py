from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .local_state import (
    LocalStateError,
    add_trusted_root,
    bootstrap_local_state,
    default_home,
    list_trusted_roots,
    remove_trusted_root,
    set_mapping,
)
from .reconcile import reconcile


def _home(value: str | None) -> Path:
    return default_home() if value is None else Path(value).expanduser().resolve()


def _ascii_safe(value: str) -> str:
    """Render arbitrary text without risking a Windows charmap encode crash."""
    try:
        value.encode(sys.stdout.encoding or "ascii")
        return value
    except UnicodeEncodeError:
        return value.encode("ascii", "backslashreplace").decode("ascii")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pwg", description="Personal Workspace Governance local toolkit")
    parser.add_argument("--home", help="Machine-local governance home (default: PWG_HOME or ~/.workspace-governance)")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Initialize machine-local governance state")
    bootstrap.add_argument("--machine-id", required=True)
    bootstrap.add_argument("--registry", required=True)

    mapping = sub.add_parser("map-set", help="Bind a registered local Surface to a local path")
    mapping.add_argument("--surface-id", required=True)
    mapping.add_argument("--path", required=True)

    trust = sub.add_parser("trust-add", help="Authorize a bounded discovery root")
    trust.add_argument("--path", required=True)
    trust.add_argument("--max-depth", type=int, default=4)
    trust.add_argument("--exclude-glob", action="append", default=[], metavar="GLOB",
                       help="Root-relative exclusion glob; repeatable")

    trust_list = sub.add_parser("trust-list", help="List machine-local trusted roots")
    trust_rm = sub.add_parser("trust-rm", help="Remove a trusted root or one of its exclusions")
    trust_rm.add_argument("--path", required=True)
    trust_rm.add_argument("--exclude-glob", default=None, metavar="GLOB",
                          help="Remove only this exclusion; omit to remove the whole root")

    status = sub.add_parser("reconcile", help="Compare registered local Surfaces with observed local reality")
    status.add_argument("--registry")
    status.add_argument("--trusted", action="store_true", help="Include explicit trusted-root discovery")
    status.add_argument("--json", action="store_true", dest="as_json")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    home = _home(args.home)
    try:
        if args.command == "bootstrap":
            bootstrap_local_state(home, args.machine_id, args.registry)
            print(f"Initialized {home} for {args.machine_id}")
        elif args.command == "map-set":
            result = set_mapping(home, args.surface_id, args.path)
            print(f"Mapped {args.surface_id}; local-map revision {result['revision']}")
        elif args.command == "trust-add":
            add_trusted_root(
                home,
                args.path,
                max_depth=args.max_depth,
                exclude_globs=args.exclude_glob,
            )
            print(f"Trusted root added: {_ascii_safe(str(Path(args.path).expanduser().resolve()))}")
        elif args.command == "trust-list":
            for item in list_trusted_roots(home):
                root_path = _ascii_safe(item["path"])
                exclusions = item.get("exclude_globs", [])
                if exclusions:
                    print(f"{root_path} (max_depth={item.get('max_depth', 4)}, "
                          f"exclude_globs={','.join(exclusions)})")
                else:
                    print(f"{root_path} (max_depth={item.get('max_depth', 4)})")
        elif args.command == "trust-rm":
            remove_trusted_root(home, args.path, exclude_glob=args.exclude_glob)
            if args.exclude_glob:
                print(f"Removed exclusion {args.exclude_glob} from {_ascii_safe(str(Path(args.path).expanduser().resolve()))}")
            else:
                print(f"Removed trusted root: {_ascii_safe(str(Path(args.path).expanduser().resolve()))}")
        elif args.command == "reconcile":
            findings = reconcile(home, args.registry, include_trusted=args.trusted)
            if args.as_json:
                print(json.dumps([item.to_dict() for item in findings], ensure_ascii=True, indent=2))
            else:
                for item in findings:
                    operation = f" -> {item.suggested_operation}" if item.suggested_operation else ""
                    print(
                        f"[{item.classification}] {item.subject_id} "
                        f"({item.confidence}, risk={item.risk}){operation}"
                    )
        return 0
    except (LocalStateError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
