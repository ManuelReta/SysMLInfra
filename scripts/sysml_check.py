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
    python scripts/sysml_check.py examples/bilgepump/Analysis.sysml
    python scripts/sysml_check.py examples/bilgepump/FMEA.sysml --expect-violations
    python scripts/sysml_check.py examples/bilgepump/Architecture.sysml --fallback
    python scripts/sysml_check.py examples/bilgepump/Requirements.sysml examples/bilgepump/Safety.sysml

Examples:
    # Quick syntax + requirement check (no kernel):
    python scripts/sysml_check.py examples/bilgepump/Analysis.sysml --fallback

    # Check a negative-test file (intentional VIOLATED assertions — exit 0):
    python scripts/sysml_check.py examples/bilgepump/FMEA.sysml --expect-violations

    # Full kernel check of a single layer:
    python scripts/sysml_check.py examples/bilgepump/Requirements.sysml
"""

from __future__ import annotations

import sys
from pathlib import Path
import sys_infra.verify as verify


# ── Manifest helpers ──────────────────────────────────────────────────────────
def _load_manifest(manifest_path: Path) -> tuple[str, list[str]]:
    """Return (project_name, ordered_layers_list)."""
    if not manifest_path.exists():
        print(f"ERROR: sysml-project.yml not found at {manifest_path}", file=sys.stderr)
        sys.exit(2)
    name, layers, _ = verify._read_manifest(str(manifest_path))
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


def _print_result(
    target: str, results: list[dict], expect_violations: bool, project_dir: Path
) -> bool:
    """
    Print per-requirement results for one target file.
    Returns True if the run counts as PASS.
    """
    violated = [r for r in results if r.get("satisfied") is False]
    unknown = [r for r in results if r.get("satisfied") is None]

    if not results:
        # Layer has no requirement defs (e.g. Library.sysml) — check file exists
        path = project_dir / target
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

    print(
        f"  ✓  {target}  [{len(results)} SATISFIED"
        + (f", {len(unknown)} UNKNOWN" if unknown else "")
        + "]"
    )
    return True


# ── Kernel check ──────────────────────────────────────────────────────────────
def _check_with_kernel(
    layer_set: list[str], project_dir: Path
) -> tuple[bool, list[dict]]:
    kernel_name = verify._discover_sysml_kernel()
    if kernel_name is None:
        print()
        print("\033[33m" + "═" * 66 + "\033[0m")
        print(
            "\033[33m  WARNING: SysML v2 kernel NOT FOUND — running Python fallback\033[0m"
        )
        print("\033[33m  " + "─" * 64 + "\033[0m")
        print("\033[33m  The fallback is for development iteration ONLY.\033[0m")
        print(
            "\033[33m  Real constraint evaluation requires the SysML v2 kernel.\033[0m"
        )
        print(
            "\033[33m  Install:  bash setup.sh  (requires Java 21 + Miniconda)\033[0m"
        )
        print("\033[33m" + "═" * 66 + "\033[0m")
        return False, []
    all_ok, _, _ = verify._run_kernel(
        layer_paths=layer_set, kernel_name=kernel_name, project_dir=project_dir
    )
    # Also run fallback to extract per-requirement results for printing
    results = verify._run_fallback(
        layer_paths=layer_set, negative=False, project_dir=project_dir
    )
    return all_ok, results


def run_check(project_dir, targets, fallback, expect_violations, verbose) -> None:
    manifest_path = project_dir / "sysml-project.yml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")
    project_name, all_layers = _load_manifest(manifest_path=manifest_path)
    print(f"\nSysML check — {project_name}")
    print("─" * 50)

    overall_pass = True
    for target in targets:
        target_norm = target.replace("\\", "/")
        layer_set = _prerequisites(target_norm, all_layers)

        # Verify the target file exists
        target_path = project_dir / target_norm
        if not target_path.exists():
            print(f"  ✗  {target_norm}  — FILE NOT FOUND", file=sys.stderr)
            overall_pass = False
            continue

        if fallback or expect_violations:
            # Python fallback: fast, no kernel startup
            if fallback:
                print()
                print("\033[33m" + "═" * 66 + "\033[0m")
                print(
                    "\033[33m  WARNING: ——fallback active — Python regex/eval only\033[0m"
                )
                print("\033[33m  " + "─" * 64 + "\033[0m")
                print("\033[33m  For development and testing ONLY.\033[0m")
                print(
                    "\033[33m  Always validate with the SysML v2 kernel before release.\033[0m"
                )
                print("\033[33m" + "═" * 66 + "\033[0m")
            results = verify._run_fallback(
                layer_set, negative=expect_violations, project_dir=project_dir
            )
        else:
            # Try kernel first; fall back to Python on kernel absence
            ok, results = _check_with_kernel(layer_set, project_dir)
            if not results:
                results = verify._run_fallback(
                    layer_set, negative=False, project_dir=project_dir
                )

        passed = _print_result(
            target=target_norm,
            results=results,
            expect_violations=expect_violations,
            project_dir=project_dir,
        )
        if verbose:
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
