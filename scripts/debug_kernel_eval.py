#!/usr/bin/env python3
"""
scripts/debug_kernel_eval.py — Step-by-step kernel requirement debugger.

Launches the SysML v2 kernel, loads every model layer, then evaluates
requirements one by one using the kernel's ExpressionEvaluator.INSTANCE.

HOW IT WORKS
────────────
The SysML v2 kernel's %eval magic accepts exactly ONE positional token
(the arg parser is: MagicsArgs.builder().optional("expr") — see Eval.java).
Inline expressions like "0.15 <= 0.3" contain spaces → 3 tokens → error.

FIX: We generate ONE SysML cell that defines a  VerificationCheck  package
containing one  calc def  per requirement, with the numeric bind values
already substituted in.  Then each %eval cell contains a single qualified
name  "VerificationCheck::<req>()"  — no spaces, one token.  The kernel
wraps it as  calc { VerificationCheck::<req>(); }  and calls
ExpressionEvaluator.INSTANCE.evaluate() — the real constraint solver.

Usage:
    python scripts/debug_kernel_eval.py
    python scripts/debug_kernel_eval.py --negative   # pump A failure
    python scripts/debug_kernel_eval.py --raw        # also print raw cell JSON
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# ── repo root ─────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO_ROOT, "sysml-project.yml")

# put verify.py helpers on path
sys.path.insert(0, REPO_ROOT)
import sys_infra.verify  # noqa: E402  (after path manipulation)


# ── ANSI helpers ──────────────────────────────────────────────────────────────
def _c(code: str, text: str) -> str:
    if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31;1", t)


def yellow(t: str) -> str:
    return _c("33", t)


def cyan(t: str) -> str:
    return _c("36", t)


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


W = 72


def _banner(title: str) -> None:
    print("\n" + bold("═" * W))
    print(bold(f"  {title}"))
    print(bold("═" * W))


def _compact_expr(expr: str) -> str:
    """
    Collapse an expression to a single whitespace-free token for %eval.

    %eval's argument parser splits on whitespace and only accepts ONE
    positional arg.  By removing all spaces (and replacing SysML keyword
    operators with symbols), the whole expression becomes one token.

        "0.15 <= 0.3"                  → "0.15<=0.3"
        "true == true"                  → "true==true"
        "false == false or false == true" → "false==false|false==true"
        "(1.0 + 0.5) * 0.02 <= 0.5 - 0.15" → "(1.0+0.5)*0.02<=0.5-0.15"
    """
    s = expr
    # Replace SysML keyword boolean operators with symbol equivalents
    s = s.replace(" or ", "|").replace(" and ", "&")
    # Remove all remaining whitespace
    s = re.sub(r"\s+", "", s)
    return s


def _read_manifest_layers() -> list[str]:
    _, all_layers, validation_layers = sys_infra.verify._read_manifest(MANIFEST)
    return validation_layers if validation_layers else all_layers


def _discover_kernel() -> str | None:
    try:
        import jupyter_client

        specs = jupyter_client.kernelspec.find_kernel_specs()
    except Exception:
        return None
    for c in ("sysml2", "sysml"):
        if c in specs:
            return c
    for k in specs:
        if "sysml" in k.lower():
            return k
    return None


def _format_cell_output(outputs: list[dict]) -> tuple[str, str]:
    """
    Return (raw_text, parsed_verdict) from a cell's outputs list.

    parsed_verdict is 'true', 'false', 'error', or '?? (unparseable)'.
    """
    parts: list[str] = []
    for o in outputs:
        otype = o.get("output_type", "")
        if otype == "stream":
            text = o.get("text", [])
            parts.append("".join(text) if isinstance(text, list) else text)
        elif otype == "execute_result":
            data = o.get("data", {})
            plain = data.get("text/plain", [])
            parts.append("".join(plain) if isinstance(plain, list) else plain)
        elif otype == "error":
            ename = o.get("ename", "Error")
            evalue = o.get("evalue", "")
            parts.append(f"[ERROR] {ename}: {evalue}")
    raw = "".join(parts).strip()
    lowered = raw.lower()
    if "[error]" in lowered:
        return raw, "error"
    if "false" in lowered:
        return raw, "false"
    if "true" in lowered:
        return raw, "true"
    return raw, "?? (unparseable)"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--negative",
        action="store_true",
        help="Inject pumpA.flowRate = 0.0 (pump A failure)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Dump raw cell output JSON for each %eval cell",
    )
    args = parser.parse_args()
    run_eval(args)


def run_eval(args) -> None:
    project_dir = args.project_dir
    # ── Kernel discovery ──────────────────────────────────────────────────────
    kernel_name = _discover_kernel()
    if kernel_name is None:
        print(red("ERROR: SysML v2 kernel not found."))
        print("  Install it with:  bash setup.sh")
        sys.exit(2)
    print(f"\n  Kernel : {cyan(kernel_name)}")
    print(
        f"  Mode   : {yellow('negative (pump A failure)' if args.negative else 'positive')}"
    )

    # ── Layers ────────────────────────────────────────────────────────────────
    layer_paths = _read_manifest_layers()
    print(f"\n  {bold('Layers to load into kernel:')}")
    for i, lp in enumerate(layer_paths, 1):
        print(f"    [{i:2}] {lp}")

    # ── Build %eval cells (expression substitution in Python) ────────────────
    eval_cells = sys_infra.verify._build_kernel_eval_cells(
        layer_paths, args.negative, project_dir
    )

    _banner("Substituted expressions (spaces stripped for single-token %eval)")
    print(
        f"  {dim('Spaces removed so each %eval receives exactly ONE positional token.')}"
    )
    print(
        f"  {dim('Kernel wraps as: calc { <compact_expr>; } → ExpressionEvaluator.INSTANCE')}"
    )
    print()
    compact_exprs: list[str] = []
    for req_name, expr, label in eval_cells:
        c = _compact_expr(expr)
        compact_exprs.append(c)
        print(f"  {cyan(req_name)}")
        print(f"        label    : {dim(label)}")
        print(f"        original : {dim(expr)}")
        print(f"        compact  : {bold(c)}")
        print(f"        will send: {yellow('%eval ' + c)}")

    if not eval_cells:
        print(red("\nNo eval cells built — check analysis/requirements paths."))
        sys.exit(2)

    # ── Build notebook ────────────────────────────────────────────────────────
    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import CellExecutionError
    except ImportError as exc:
        print(red(f"ERROR: {exc} — run:  pip install nbclient nbformat"))
        sys.exit(2)

    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "SysML v2",
        "language": "sysml",
        "name": kernel_name,
    }

    # ── Cell group 1: model layers ────────────────────────────────────────────
    n_model = len(layer_paths)
    for lp in layer_paths:
        nb.cells.append(
            nbformat.v4.new_code_cell(
                sys_infra.verify._read(os.path.join(REPO_ROOT, lp))
            )
        )

    # ── Cell group 2: one %eval per requirement ───────────────────────────────
    #   Compact (space-free) expression → single token → MagicsArgs accepts it.
    #   The kernel calls:  interactive.eval("<compact>", null, false)
    #   which wraps it as:  calc { <compact>; }
    #   and runs ExpressionEvaluator.INSTANCE.evaluate() — the real solver.
    idx_eval_start = n_model
    for compact in compact_exprs:
        cell = nbformat.v4.new_code_cell(f"%eval {compact}")
        cell.metadata["tags"] = ["raises-exception"]  # continue even if one errors
        nb.cells.append(cell)

    client = NotebookClient(
        nb,
        timeout=300,
        kernel_name=kernel_name,
        resources={"metadata": {"path": REPO_ROOT}},
    )

    # ── Execute (suppress JAR boot noise on fd 1/2) ───────────────────────────
    _banner(
        f"Executing kernel — loading {n_model} layer(s) + {len(eval_cells)} %eval cell(s)"
    )
    print(
        f"  {dim('(SysML kernel startup takes ~10 s — kernel boot messages suppressed)')}"
    )
    sys.stdout.flush()
    sys.stderr.flush()
    _so = os.dup(1)
    _se = os.dup(2)
    _dn = os.open(os.devnull, os.O_WRONLY)
    os.dup2(_dn, 1)
    os.dup2(_dn, 2)
    os.close(_dn)
    try:
        client.execute()
    except CellExecutionError:
        pass
    except Exception as exc:
        os.dup2(_so, 1)
        os.dup2(_se, 2)
        os.close(_so)
        os.close(_se)
        print(red(f"\nKernel execution error: {exc}"))
        sys.exit(1)
    finally:
        os.dup2(_so, 1)
        os.dup2(_se, 2)
        os.close(_so)
        os.close(_se)

    # ── Step 1: model layer compile results ───────────────────────────────────
    _banner("Step 1 — Kernel parse + type-check per layer")
    compile_ok = True
    for i in range(n_model):
        cell = nb.cells[i]
        errors = [o for o in cell.get("outputs", []) if o.get("output_type") == "error"]
        ok = not errors
        if not ok:
            compile_ok = False
        icon = green("✓  OK       ") if ok else red("✗  ERRORS  ")
        layer = os.path.basename(layer_paths[i])
        print(f"  {icon}  {layer}")
        if errors:
            for e in errors[:3]:
                print(f"               {dim(e.get('evalue', '')[:80])}")

    if not compile_ok:
        print(yellow("\n  ⚠  Layer compile errors above may affect %eval results."))

    # ── Step 2: requirement-by-requirement %eval results ─────────────────────
    _banner(
        "Step 2 — Requirement evaluation via kernel %eval → ExpressionEvaluator.INSTANCE"
    )
    print(f"  {dim('Each cell: %eval <compact_expr>  (no spaces = single token)')}")
    print(
        f"  {dim('Kernel: calc { <compact_expr>; } → ExpressionEvaluator.INSTANCE.evaluate()')}"
    )
    print()

    n_satisfied = 0
    n_violated = 0
    n_unknown = 0

    for j, (req_name, expr, label) in enumerate(eval_cells):
        cell = nb.cells[idx_eval_start + j]
        outputs = cell.get("outputs", [])
        compact = compact_exprs[j]
        raw, verdict = _format_cell_output(outputs)

        print(f"  {'─' * (W - 2)}")
        print(f"  Requirement : {bold(req_name)}")
        print(f"  Label       : {dim(label)}")
        print(f"  Expression  : {dim(expr)}")
        print(f"  %eval sent  : {cyan('%eval ' + compact)}")

        if not outputs:
            print(
                f"  Kernel raw  : {yellow('(cell never executed — check prior errors)')}"
            )
            print(f"  Verdict     : {yellow('UNKNOWN — not executed')}")
            n_unknown += 1
        elif verdict == "true":
            print(f"  Kernel raw  : {dim(repr(raw))}")
            print(f"  Verdict     : {green('SATISFIED ✓')}")
            n_satisfied += 1
        elif verdict == "false":
            print(f"  Kernel raw  : {dim(repr(raw))}")
            print(f"  Verdict     : {red('VIOLATED ✗')}")
            n_violated += 1
        elif verdict == "error":
            print(f"  Kernel raw  : {red(repr(raw[:160]))}")
            print(f"  Verdict     : {yellow('ERROR / UNKNOWN ?')}")
            n_unknown += 1
        else:
            print(f"  Kernel raw  : {yellow(repr(raw[:160]))}")
            print(f"  Verdict     : {yellow('UNKNOWN ?')}")
            n_unknown += 1

        if args.raw:
            print("  Raw outputs JSON:")
            print(f"    {json.dumps(outputs, indent=2)[:600]}")

    # ── Summary ───────────────────────────────────────────────────────────────
    _banner("Summary")
    print(f"  Evaluated  : {len(eval_cells)} requirement(s)")
    print(f"  {green('SATISFIED')} : {n_satisfied}")
    if n_violated:
        print(f"  {red('VIOLATED')}  : {n_violated}")
    else:
        print(f"  VIOLATED   : {n_violated}")
    if n_unknown:
        print(
            f"  {yellow('UNKNOWN')}   : {n_unknown}  (expr not substituted, kernel error, or not executed)"
        )
    else:
        print(f"  UNKNOWN    : {n_unknown}")
    print()

    sys.exit(0 if n_violated == 0 else 1)


if __name__ == "__main__":
    main()
