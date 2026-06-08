#!/usr/bin/env python3
"""
sysml_check.py — Lightweight SysML v2 file checker for local development.

Validates one or more .sysml files by running them through the Python fallback
evaluator (regex + eval) or the SysML v2 kernel.  Faster than verify.py for
checking a single layer without evaluating the full verification matrix.

For each target file, the script automatically collects all prerequisite layers
(as declared in sysml-project.yml) and includes them in the run, ensuring that
imports resolve correctly.

Exit codes:
  0 — all targets PASS (no violations, no errors)
  1 — at least one target FAIL or VIOLATED
  2 — configuration error (missing manifest, file not found)

Usage:
    python scripts/sysml_check.py bilgepump/Analysis.sysml
    python scripts/sysml_check.py bilgepump/FMEA.sysml --expect-violations
    python scripts/sysml_check.py bilgepump/Architecture.sysml --fallback
    python scripts/sysml_check.py bilgepump/Requirements.sysml bilgepump/Safety.sysml

Examples:
    # Quick syntax + requirement check (no kernel):
    python scripts/sysml_check.py bilgepump/Analysis.sysml --fallback

    # Check a negative-test file (intentional VIOLATED assertions — exit 0):
    python scripts/sysml_check.py bilgepump/FMEA.sysml --expect-violations

    # Full kernel check of a single layer:
    python scripts/sysml_check.py bilgepump/Requirements.sysml
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
MANIFEST  = REPO_ROOT / "sysml-project.yml"

# Allow importing verify.py helpers from the repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import verify


# ── Manifest helpers ──────────────────────────────────────────────────────────

def _load_manifest() -> tuple[str, list[str]]:
    """Return (project_name, ordered_layers_list)."""
    if not MANIFEST.exists():
        print(f"ERROR: sysml-project.yml not found at {MANIFEST}", file=sys.stderr)
        sys.exit(2)
    name, layers, _ = verify._read_manifest(str(MANIFEST))
    if not layers:
        print("ERROR: sysml-project.yml contains no layers entries.", file=sys.stderr)
        sys.exit(2)
    return name, layers


def _prerequisites(target: str, all_layers: list[str]) -> list[str]:
    """
    Return all layers that appear before 'target' in the manifest order,
    plus 'target' itself.  Ensures imports resolve when running a single file.
    """
    target_norm = target.replace("\\", "/")
    result: list[str] = []
    for layer in all_layers:
        result.append(layer)
        if layer.replace("\\", "/") == target_norm:
            return result
    # target not in manifest — include all layers + the target as a free-standing file
    result.append(target)
    return result


# ── Output helpers ────────────────────────────────────────────────────────────

def _print_result(target: str, results: list[dict], expect_violations: bool) -> bool:
    """
    Print per-requirement results for one target file.
    Returns True if the run counts as PASS.
    """
    violated = [r for r in results if r.get("satisfied") is False]
    unknown  = [r for r in results if r.get("satisfied") is None]

    if not results:
        # Layer has no requirement defs (e.g. Library.sysml) — check file exists
        path = REPO_ROOT / target
        if path.exists():
            print(f"  ✓  {target}  (no requirements to evaluate)")
            return True
        else:
            print(f"  ✗  {target}  — FILE NOT FOUND", file=sys.stderr)
            return False

    if expect_violations:
        # Negative-test mode: PASS if at least one is violated (as intended)
        if violated:
            print(f"  ✓  {target}  [{len(violated)} expected violation(s)]")
            return True
        else:
            print(f"  ✗  {target}  — expected violations but none found")
            return False

    if violated:
        print(f"  ✗  {target}  [{len(violated)} VIOLATED]")
        for r in violated:
            print(f"       VIOLATED  {r.get('label', r['requirement'])}")
        return False

    print(f"  ✓  {target}  [{len(results)} SATISFIED"
          + (f", {len(unknown)} UNKNOWN" if unknown else "") + "]")
    return True


# ── Kernel check ──────────────────────────────────────────────────────────────

def _check_with_kernel(layer_set: list[str]) -> tuple[bool, list[dict]]:
    kernel_name = verify._discover_sysml_kernel()
    if kernel_name is None:
        print("WARNING: No SysML v2 kernel found — falling back to Python evaluator.",
              file=sys.stderr)
        return False, []
    all_ok, _ = verify._run_kernel(layer_set, kernel_name)
    # Also run fallback to extract per-requirement results for printing
    results = verify._run_fallback(layer_set, negative=False)
    return all_ok, results


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sysml_check.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "targets",
        nargs="+",
        metavar="FILE.sysml",
        help="One or more .sysml files to check (relative to repo root).",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Use Python regex/eval only; skip the SysML v2 kernel.",
    )
    parser.add_argument(
        "--expect-violations",
        action="store_true",
        help="Negative-test mode: PASS when at least one requirement is VIOLATED.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show constraint expression for each requirement.",
    )
    args = parser.parse_args()

    project_name, all_layers = _load_manifest()
    print(f"\nSysML check — {project_name}")
    print("─" * 50)

    overall_pass = True
    for target in args.targets:
        target_norm = target.replace("\\", "/")
        layer_set   = _prerequisites(target_norm, all_layers)

        # Verify the target file exists
        target_path = REPO_ROOT / target_norm
        if not target_path.exists():
            print(f"  ✗  {target_norm}  — FILE NOT FOUND", file=sys.stderr)
            overall_pass = False
            continue

        if args.fallback or args.expect_violations:
            # Python fallback: fast, no kernel startup
            results = verify._run_fallback(layer_set, negative=args.expect_violations)
        else:
            # Try kernel first; fall back to Python on kernel absence
            ok, results = _check_with_kernel(layer_set)
            if not results:
                results = verify._run_fallback(layer_set, negative=False)

        passed = _print_result(target_norm, results, args.expect_violations)
        if args.verbose:
            for r in results:
                if r.get("expr"):
                    print(f"         expr: {r['expr'][:80]}")
        overall_pass = overall_pass and passed

    print("─" * 50)
    if overall_pass:
        print("PASS\n")
        sys.exit(0)
    else:
        print("FAIL\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
