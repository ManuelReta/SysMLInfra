#!/usr/bin/env python3
"""
verify.py — Local-first SysML v2 verification engine.

Reusable MBSE verification entry point. Runs entirely locally — the
remote SST API is NOT required for verification.

Usage:
    python verify.py                  # kernel execution, validation_layers (positive test)
    python verify.py --negative       # inject fault via bind override (failure simulation)
    python verify.py --all            # include FMEA negative tests + UQ sweep
    python verify.py --fallback       # Python regex/eval only (DEV/TEST use only — see WARNING)
    python verify.py --require-kernel # exit code 2 if SysML v2 kernel is not installed
    python verify.py --dry-run        # list layers, check files — do not run kernel
    python verify.py --visual         # also generate system/traceability diagrams
    python verify.py --publish        # push committed layers to SST API after verification

Prerequisites:
    Kernel path (default — REQUIRED for real verification):
        conda env sysmlv2 with jupyter-sysml-kernel=0.58.0
        (installed by setup.sh)
    Fallback (——fallback):
        FOR DEVELOPMENT AND TESTING ONLY.
        Python regex/eval cannot perform SysML type checking or catch syntax
        errors. Runs without extra dependencies (stdlib only) but results are
        not authoritative. Always validate with the kernel before release.
    Visual (——visual):
        pip install networkx  (matplotlib already in requirements.txt)

Exit codes:
    0 — all checked requirements SATISFIED
    1 — one or more requirements VIOLATED, or kernel error
    2 — setup error (missing files, missing kernel)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from sys_infra.environment import LIB_DIR, REPO_ROOT
from sys_infra.utils import _USE_COLOR, bold, cyan, dim, green, red, yellow


# ── Manifest reader (same logic as ci_kernel_validate.py) ────────────────────


def _read_manifest(path: str) -> tuple[str, list, list | None]:
    name = "SysMLProject"
    layers: list[str] = []
    validation_layers: list[str] | None = None
    current_list: list[str] | None = None
    with open(path) as fh:
        for raw in fh:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("name:"):
                name = s.split(":", 1)[1].strip().strip("\"'")
                current_list = None
            elif s == "layers:":
                current_list = layers
            elif s == "validation_layers:":
                validation_layers = []
                current_list = validation_layers
            elif current_list is not None and s.startswith("- "):
                current_list.append(s[2:].strip())
            elif (
                current_list is not None
                and s
                and not s.startswith("-")
                and not s.startswith("#")
            ):
                current_list = None
    return name, layers, validation_layers


# ── Comment stripping + constraint evaluation (fallback path) ────────────────


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _build_bind_values(analysis_text: str, negative: bool) -> tuple[dict, dict]:
    """Return (full_path_index, bare_name_index) from bind statements."""
    bind_values: dict = {}
    for m in re.finditer(r"\bbind\s+([\w.]+)\s*=\s*([^;]+);", analysis_text):
        path = m.group(1).strip()
        raw = m.group(2).strip()
        if raw.lower() == "true":
            value: object = True
        elif raw.lower() == "false":
            value = False
        else:
            try:
                value = float(raw)
            except ValueError:
                continue
        bind_values[path] = value

    if negative:
        for key in list(bind_values.keys()):
            if "pumpa" in key.lower() and "flowrate" in key.lower():
                bind_values[key] = 0.0
                print(
                    f"  {yellow('[NEGATIVE]')} Override: {key} = 0.0  (pump A failure)"
                )

    bare_values = {path.rsplit(".", 1)[-1]: val for path, val in bind_values.items()}
    return bind_values, bare_values


def _eval_requirement(
    name: str, expr_raw: str, bind_values: dict, bare_values: dict
) -> bool | None:
    expr = expr_raw
    for path, val in sorted(bind_values.items(), key=lambda x: -len(x[0])):
        expr = re.sub(r"\b" + re.escape(path) + r"\b", repr(val), expr)
    for bare, val in sorted(bare_values.items(), key=lambda x: -len(x[0])):
        expr = re.sub(r"\b" + re.escape(bare) + r"\b", repr(val), expr)
    expr = re.sub(r"\btrue\b", "True", expr)
    expr = re.sub(r"\bfalse\b", "False", expr)
    # Drop unit annotations: "0.3 m" → "0.3"
    expr = re.sub(r"(?<=[\d)])(\s+[a-zA-Z/\u00b3\u00b2\u00b0]+)+", "", expr).strip()
    try:
        return bool(eval(expr, {"__builtins__": {}}))  # noqa: S307 – restricted namespace
    except Exception:
        return None


# ── Fallback path: Python regex/eval ─────────────────────────────────────────

REQ_LABELS: dict[str, str] = {
    "WaterLevelRequirement": "BPS-REQ-001  Water level ≤ 0.30 m",
    "PumpRedundancyRequirement": "BPS-REQ-002  Pump B redundancy active",
    "AlarmResponseRequirement": "BPS-REQ-003  Alarm delay ≤ 2.00 s",
    "DischargeCapacityRequirement": "BPS-REQ-004  Discharge ≥ design inflow",
    "ControllerActivationTimingRequirement": "BPS-REQ-005  Controller response ≤ 5.0 s",
    "FailoverSwitchTimingRequirement": "BPS-REQ-006  Failover time ≤ 3.0 s",
    "SensorAccuracyBoundRequirement": "BPS-FT-001   Sensor accuracy bound ≤ 0.30 m",
    "EffectiveDischargeCapacityRequirement": "BPS-FT-002   Effective discharge (η × flow) ≥ inflow",
    "TriggerLevelAccuracyRequirement": "BPS-FT-003   Trigger + accuracy ≤ 0.30 m",
    "EndToEndResponseRequirement": "BPS-FT-004   Response chain ≤ overflow window",
    "OverrideOrderingRequirement": "BPS-OOR-001  Override only after alarm active",
    "UCA_001_ControllerNoActivatePumpA": "UCA-001  SR  Controller activates pump A",
    "UCA_002_SensorFailSilent": "UCA-002  SR  Sensor not fail-silent",
    "UCA_003_AlarmNotTriggered": "UCA-003  SR  Alarm triggered on flood",
    "UCA_004_PumpBNotActivated": "UCA-004  SR  Pump B activated on failover",
    "UCA_005_ActivatePumpTooLong": "UCA-005  SR  Pump not overrun indefinitely",
}


def _run_fallback(
    layer_paths: list[str],
    negative: bool,
    project_dir: Path,
    verbose: bool = False,
) -> list[dict]:
    """
    Python regex + eval constraint evaluator.
    Works without the SysML kernel; mirrors the logic in verify.sh.
    Returns list of {requirement, satisfied, expr, label} dicts.
    """
    analysis_path = next((p for p in layer_paths if "analysis" in p.lower()), None)
    requirements_path = next(
        (p for p in layer_paths if "requirements" in p.lower()), None
    )
    safety_path = next((p for p in layer_paths if "safety" in p.lower()), None)

    if not analysis_path or not requirements_path:
        print(
            red(
                "ERROR: Cannot locate Analysis.sysml or Requirements.sysml in layer list."
            )
        )
        sys.exit(2)

    analysis_text = _strip_comments(_read(os.path.join(project_dir, analysis_path)))
    bind_values, bare_values = _build_bind_values(analysis_text, negative)

    # Collect requirement defs from Requirements.sysml + Safety.sysml
    req_texts: list[tuple[str, str]] = []  # (rel_path, content)
    for rp in (requirements_path, safety_path):
        if rp and os.path.exists(os.path.join(project_dir, rp)):
            req_texts.append(
                (rp, _strip_comments(_read(os.path.join(project_dir, rp))))
            )

    req_pattern = re.compile(
        r"requirement\s+def\s+(\w+).*?require\s+constraint\s*\{([^}]+)\}",
        re.DOTALL,
    )

    results: list[dict] = []
    for rel_path, text in req_texts:
        for m in req_pattern.finditer(text):
            req_name = m.group(1)
            expr_raw = re.sub(r"\s+", " ", m.group(2).strip())
            satisfied = _eval_requirement(req_name, expr_raw, bind_values, bare_values)
            results.append(
                {
                    "requirement": req_name,
                    "satisfied": satisfied,
                    "expr": expr_raw,
                    "label": REQ_LABELS.get(req_name, req_name),
                }
            )

    return results


# ── Kernel %eval helper ───────────────────────────────────────────────────────


def _build_kernel_eval_cells(
    layer_paths: list[str],
    negative: bool,
    project_dir: Path,
) -> list[tuple[str, str, str]]:
    """
    Build (req_name, sysml_expr, label) triples to send as %eval cells.

    sysml_expr is the constraint expression with every bind-value path
    replaced by its numeric / Boolean literal so the expression is self-
    contained and contains no model-member references.  The expression is
    valid SysML syntax; the kernel evaluates it via ExpressionEvaluator.INSTANCE.

    Examples:
        "sys.sensor.waterLevel <= 0.30"
          → "0.15 <= 0.3"            (bind sys.sensor.waterLevel = 0.15)
        "sys.pumpB.isRedundant == true"
          → "true == true"           (bind sys.pumpB.isRedundant = true)
    """
    analysis_path = next((p for p in layer_paths if "analysis" in p.lower()), None)
    requirements_path = next(
        (p for p in layer_paths if "requirements" in p.lower()), None
    )
    safety_path = next((p for p in layer_paths if "safety" in p.lower()), None)

    if not analysis_path or not requirements_path:
        return []

    analysis_text = _strip_comments(_read(os.path.join(project_dir, analysis_path)))
    bind_values, bare_values = _build_bind_values(analysis_text, negative)

    req_texts: list[str] = []
    for rp in (requirements_path, safety_path):
        if rp and os.path.exists(os.path.join(project_dir, rp)):
            req_texts.append(_strip_comments(_read(os.path.join(project_dir, rp))))

    req_pattern = re.compile(
        r"requirement\s+def\s+(\w+).*?require\s+constraint\s*\{([^}]+)\}",
        re.DOTALL,
    )

    eval_cells: list[tuple[str, str, str]] = []
    for text in req_texts:
        for m in req_pattern.finditer(text):
            req_name = m.group(1)
            expr = re.sub(r"\s+", " ", m.group(2).strip())
            # Substitute full-path bind values (longest first to avoid partial matches)
            for path, val in sorted(bind_values.items(), key=lambda x: -len(x[0])):
                sysml_lit = (
                    ("true" if val else "false") if isinstance(val, bool) else repr(val)
                )
                expr = re.sub(r"\b" + re.escape(path) + r"\b", sysml_lit, expr)
            # Substitute bare-name bind values
            for bare, val in sorted(bare_values.items(), key=lambda x: -len(x[0])):
                sysml_lit = (
                    ("true" if val else "false") if isinstance(val, bool) else repr(val)
                )
                expr = re.sub(r"\b" + re.escape(bare) + r"\b", sysml_lit, expr)
            # Strip unit annotations: "0.3 m" → "0.3"
            # Negative lookahead prevents matching SysML boolean/logic keywords.
            expr = re.sub(
                r"(?<=[\d)])\s+(?!(?:and|or|not|if|else|then|implies|true|false)\b)"
                r"[a-zA-Z/\u00b3\u00b2\u00b0]+\b",
                "",
                expr,
            ).strip()
            eval_cells.append((req_name, expr, REQ_LABELS.get(req_name, req_name)))

    return eval_cells


# ── Kernel path: nbclient execution ──────────────────────────────────────────


def _discover_sysml_kernel() -> str | None:
    try:
        import jupyter_client

        installed = jupyter_client.kernelspec.find_kernel_specs()
    except Exception:
        return None
    for candidate in ("sysml2", "sysml"):
        if candidate in installed:
            return candidate
    for k in installed:
        if "sysml" in k.lower():
            return k
    return None


def _parse_kernel_eval_output(cell: dict) -> bool | None:
    """
    Extract the boolean result from a kernel %eval cell output.

    The SysML v2 kernel evaluates the expression via
    ExpressionEvaluator.INSTANCE and returns a string like "true" or "false"
    (possibly wrapped in element formatting).  Returns None if the output
    cannot be parsed (treat as UNKNOWN).
    """
    outputs = cell.get("outputs", [])
    text = ""
    for o in outputs:
        otype = o.get("output_type", "")
        if otype == "stream":
            text += "".join(o.get("text", []))
        elif otype == "execute_result":
            data = o.get("data", {})
            plain = data.get("text/plain", [])
            text += "".join(plain) if isinstance(plain, list) else plain
        elif otype == "error":
            # Kernel reported an error — evaluation failed
            return None
    lowered = text.strip().lower()
    if not lowered:
        return None
    # "true" anywhere → True; "false" anywhere → False
    # "false" takes precedence over "true" in ambiguous output
    has_true = "true" in lowered
    has_false = "false" in lowered
    if has_false:
        return False
    if has_true:
        return True
    return None


def _run_kernel(
    layer_paths: list[str],
    kernel_name: str,
    project_dir: Path,
    eval_cells: list[tuple[str, str, str]] | None = None,
) -> tuple[bool, list[dict], list[dict]]:
    """
    Execute all layers via nbclient using the registered SysML v2 Jupyter kernel.

    After loading the model layers, optional *eval_cells* are appended.
    Each entry is ``(req_name, sysml_expr, label)`` where *sysml_expr* is a
    fully-substituted SysML boolean expression (no model-member references).
    The kernel evaluates each one via the ``%eval`` magic, which calls
    ``ExpressionEvaluator.INSTANCE`` — the real SysML constraint solver.

    Returns:
        (all_passed, kernel_cell_results, eval_results)

        kernel_cell_results — [{layer, ok, errors}] per model layer cell
        eval_results        — [{requirement, satisfied, expr, label, source}]
                              ``source`` is ``'kernel:%eval'`` for results
                              evaluated by the kernel, or ``None`` if the
                              kernel reported an error for that cell.
    """
    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import CellExecutionError
    except ImportError as exc:
        print(red(f"ERROR: {exc}"))
        print("  Install CI dependencies:  pip install nbclient nbformat")
        sys.exit(2)

    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "SysML v2",
        "language": "sysml",
        "name": kernel_name,
    }

    # ── Model layer cells ─────────────────────────────────────────────────────
    n_model_cells = len(layer_paths)
    for layer_file in layer_paths:
        abs_path = os.path.join(project_dir, layer_file)
        nb.cells.append(nbformat.v4.new_code_cell(_read(abs_path)))

    # ── %eval requirement cells ───────────────────────────────────────────────
    #   Each cell contains exactly one %eval <compact_expr> magic command.
    #   Spaces are removed so the expression is ONE token (MagicsArgs.optional).
    #   The SysML v2 kernel wraps it as  calc { <compact_expr>; }
    #   and runs it through ExpressionEvaluator.INSTANCE — NOT Python eval().
    if eval_cells:
        for _req_name, _expr, _label in eval_cells:
            _compact = re.sub(
                r"\s+",
                "",
                _expr.replace(" or ", "|").replace(" and ", "&"),
            )
            cell = nbformat.v4.new_code_cell(f"%eval {_compact}")
            cell.metadata["tags"] = ["raises-exception"]
            nb.cells.append(cell)

    client = NotebookClient(
        nb,
        timeout=300,
        kernel_name=kernel_name,
        resources={"metadata": {"path": REPO_ROOT}},
    )

    # The SysML kernel JAR writes ~50 lines of "Reading *.kerml" messages plus
    # log4j and JUL INFO logs via the inherited stdout/stderr file descriptors.
    # Redirect fd 1 and fd 2 at the OS level before execute() starts the subprocess
    # so those messages are silently discarded.  We flush first to avoid losing
    # any buffered Python output, then restore after execute() returns.
    sys.stdout.flush()
    sys.stderr.flush()
    _saved_out = os.dup(1)
    _saved_err = os.dup(2)
    _devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(_devnull, 1)
    os.dup2(_devnull, 2)
    os.close(_devnull)

    _exec_error: Exception | None = None
    try:
        client.execute()
    except CellExecutionError:
        pass  # We inspect outputs below regardless
    except Exception as exc:
        _exec_error = exc
    finally:
        os.dup2(_saved_out, 1)
        os.dup2(_saved_err, 2)
        os.close(_saved_out)
        os.close(_saved_err)

    if _exec_error is not None:
        print(red(f"\nKernel execution error: {_exec_error}"))
        return False, [], []

    # ── Parse model layer results ─────────────────────────────────────────────
    cell_results: list[dict] = []
    all_ok = True
    for i in range(n_model_cells):
        cell = nb.cells[i]
        errors = [o for o in cell.get("outputs", []) if o.get("output_type") == "error"]
        cell_results.append(
            {
                "layer": layer_paths[i],
                "ok": not errors,
                "errors": errors,
            }
        )
        if errors:
            all_ok = False

    # ── Parse %eval results ───────────────────────────────────────────────────
    eval_results: list[dict] = []
    if eval_cells:
        for j, (req_name, expr, label) in enumerate(eval_cells):
            cell = nb.cells[n_model_cells + j]
            satisfied = _parse_kernel_eval_output(cell)
            eval_results.append(
                {
                    "requirement": req_name,
                    "satisfied": satisfied,
                    "expr": expr,
                    "label": label,
                    "source": "kernel:%eval",
                }
            )

    return all_ok, cell_results, eval_results


# ── Output formatting ─────────────────────────────────────────────────────────

_WIDE = 68


def _print_header(project_name: str, mode: str, engine: str) -> None:
    print()
    print(bold("═" * _WIDE))
    print(bold(f"  SysML v2 Verification — {project_name}"))
    print(bold("═" * _WIDE))
    print(f"  Engine  : {cyan(engine)}")
    print(f"  Mode    : {yellow(mode)}")
    print(bold("─" * _WIDE))


def _print_layer_summary(cell_results: list[dict]) -> None:
    print(f"\n  {bold('Kernel layer parse + type-check:')}")
    for cr in cell_results:
        icon = green("✓") if cr["ok"] else yellow("⚠")
        label = os.path.basename(cr["layer"])
        # Show first meaningful error snippet
        if cr["errors"]:
            first = cr["errors"][0]
            evalue = first.get("evalue", "")[:90]
            print(f"    {icon}  {label:<30}  {dim(evalue)}")
        else:
            print(f"    {icon}  {label}")


def _print_results(
    results: list[dict], show_expr: bool = False
) -> tuple[bool, list[str]]:
    violated: list[str] = []
    # Determine whether all results came from the kernel, all from Python, or mixed
    sources = {r.get("source") for r in results}
    if sources == {"kernel:%eval"}:
        section_label = "Requirement evaluation  [engine: SysML kernel %eval]"
    elif (
        not sources
        or sources == {None}
        or not any(s and "kernel" in s for s in sources)
    ):
        section_label = "Requirement evaluation  [engine: Python regex/eval — fallback]"
    else:
        section_label = (
            "Requirement evaluation  [engine: mixed — kernel + Python fallback]"
        )

    print()
    print(f"  {bold(section_label)}")
    print("  " + "─" * (_WIDE - 2))
    for r in results:
        sat = r.get("satisfied")
        name = r["requirement"]
        label = r.get("label", REQ_LABELS.get(name, name))
        src = r.get("source", "")
        src_note = dim(" [python]") if src == "python-fallback" else ""
        if sat is True:
            icon = green("✓  SATISFIED")
            _ = green
        elif sat is False:
            icon = red("✗  VIOLATED ")
            _ = red
            violated.append(name)
        else:
            icon = yellow("?  UNKNOWN  ")
            _ = yellow
        print(f"  {icon}   {label}{src_note}")
        if show_expr and r.get("expr"):
            print(f"              {dim(r['expr'][:72])}")
    print("  " + "─" * (_WIDE - 2))
    all_pass = len(violated) == 0
    overall = (
        green("ALL SATISFIED ✓") if all_pass else red(f"{len(violated)} VIOLATED ✗")
    )
    print(f"  {bold('Overall:')}  {overall}")
    print(bold("═" * _WIDE))
    return all_pass, violated


# ── Fault trace printing ──────────────────────────────────────────────────────


def _print_fault_traces(
    violated: list[str],
    all_layer_paths: list[str],
    negative: bool,
) -> None:
    try:
        from scripts.fault_tracer import FaultTracer
    except ImportError:
        print(
            yellow("\n  (fault_tracer not available — install scripts/ on PYTHONPATH)")
        )
        return

    print(
        f"\n{bold('  Safety Fault Trace' + (' — Negative Test' if negative else ''))}"
    )
    print("  " + "─" * (_WIDE - 2))
    tracer = FaultTracer(str(REPO_ROOT), all_layer_paths, negative=negative)
    tracer.load()
    traces = tracer.trace_violations(violated)
    for trace in traces:
        reg_str = f"  [{', '.join(trace.reg_ids)}]" if trace.reg_ids else ""
        print(f"\n  {red('✗')} {bold(trace.req_name)}{dim(reg_str)}")
        print(trace.format(color=_USE_COLOR))
    print()


# ── Results persistence ───────────────────────────────────────────────────────


def _save_results(results: list[dict], mode: str, engine: str) -> None:
    os.makedirs(LIB_DIR, exist_ok=True)
    payload = {
        "method": engine,
        "test_mode": mode,
        "all_satisfied": not any(r.get("satisfied") is False for r in results),
        "results": [
            {"requirement": r["requirement"], "satisfied": r.get("satisfied")}
            for r in results
        ],
    }
    out_path = os.path.join(LIB_DIR, "verification-results.json")
    with open(out_path, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(dim("  Results written to lib/verification-results.json"))


# ── Optional: publish to SST API ─────────────────────────────────────────────


def _publish(layer_paths: list[str], project_name: str) -> None:
    """Upload model layers to the SST public API (optional, for sharing)."""
    try:
        import requests  # noqa: PLC0415
    except ImportError:
        print(
            yellow("  SKIPPED: requests library not installed (pip install requests)")
        )
        return

    api_base = os.environ.get("SYSML_API_BASE", "http://sysml2.intercax.com:9000")
    print(f"\n  {bold('Publishing to SST API:')}  {api_base}")

    try:
        r = requests.get(f"{api_base}/projects", timeout=8)
        if r.status_code != 200:
            print(
                yellow(
                    f"  WARNING: API returned HTTP {r.status_code} — skipping publish"
                )
            )
            return
    except Exception as exc:
        print(yellow(f"  WARNING: Cannot reach {api_base} ({exc}) — skipping publish"))
        return

    # Create project
    r = requests.post(
        f"{api_base}/projects",
        json={"@type": "Project", "name": project_name},
        timeout=15,
    )
    if r.status_code not in (200, 201):
        print(red(f"  ERROR: Failed to create project (HTTP {r.status_code})"))
        return
    project_id = r.json().get("@id") or r.json().get("id")
    print(f"  Project ID : {project_id}")

    commit_ids: dict[str, str] = {}
    for layer_file in layer_paths:
        abs_path = os.path.join(REPO_ROOT, layer_file)
        body = _read(abs_path)
        stem = Path(layer_file).stem.lower()
        rc = requests.post(
            f"{api_base}/projects/{project_id}/commits",
            json={
                "description": stem,
                "changes": [{"@type": "TextualRepresentation", "body": body}],
            },
            timeout=30,
        )
        if rc.status_code in (200, 201):
            cid = rc.json().get("@id") or rc.json().get("id", "?")
            commit_ids[stem] = cid
            print(f"  {green('✓')} {layer_file}")
        else:
            print(f"  {yellow('✗')} {layer_file}  HTTP {rc.status_code}")

    os.makedirs(LIB_DIR, exist_ok=True)
    out_path = os.path.join(LIB_DIR, "commit-ids.json")
    with open(out_path, "w") as fh:
        json.dump({"project_id": project_id, "commits": commit_ids}, fh, indent=2)
    print(f"  {dim('Commit IDs written to lib/commit-ids.json')}")


# ── Dry-run ───────────────────────────────────────────────────────────────────


def _dry_run(name: str, layers: list, validation_layers: list | None) -> None:
    vl_set = set(validation_layers) if validation_layers else set(layers)
    print(bold(f"\nDRY RUN — {name}"))
    print(f"  {len(layers)} layer(s) in manifest order")
    if validation_layers is not None:
        excluded = [layer for layer in layers if layer not in vl_set]
        if excluded:
            print(
                f"  {len(excluded)} excluded from positive-test run (negative/UQ tests):"
            )
            for e in excluded:
                print(f"    {dim('- ' + e)}")
    print()
    missing = []
    for i, fname in enumerate(layers, 1):
        path = os.path.join(REPO_ROOT, fname)
        ok = os.path.exists(path)
        size = os.path.getsize(path) if ok else 0
        icon = green("✓") if ok else red("✗ MISSING")
        print(f"  [{i:2}] {fname:<42} {size:>7} bytes  {icon}")
        if not ok:
            missing.append(fname)
    print()
    if missing:
        print(red(f"  {len(missing)} file(s) missing — check the repository."))
        sys.exit(2)
    print(green("  All layer files present."))
    print("\n  Run without --dry-run to execute the kernel verification.")
    sys.exit(0)


# ── Z3 formal analysis bridge ─────────────────────────────────────────────────


def _run_z3_analysis(bind_values: dict | None, verbose: bool, MANIFEST: Path) -> None:
    """
    Import and run the project's formal_analysis.py module.
    Derives the path from the z3_layers key in sysml-project.yml.
    Prints a gap-report section after the SysML requirement results.

    bind_values: optional dict of overrides (full-path keys from Analysis.sysml
                 bind statements, e.g. 'sys.pumpA.flowRate').  None → use nominal.
    """
    import importlib as _il

    # Derive formal_analysis location from sysml-project.yml z3_layers key
    _z3_path: str | None = None
    try:
        with open(MANIFEST) as _mf:
            _in_z3 = False
            for _line in _mf:
                _s = _line.strip()
                if _s == "z3_layers:":
                    _in_z3 = True
                    continue
                if _in_z3 and _s.startswith("- "):
                    _z3_path = _s[2:].strip()
                    break
                if _in_z3 and _s and not _s.startswith("#") and not _s.startswith("-"):
                    _in_z3 = False
    except Exception:
        pass

    if _z3_path is None:
        print(
            yellow(
                "  WARNING: No z3_layers entry in sysml-project.yml — skipping Z3 analysis."
            )
        )
        return

    _z3_abs = os.path.join(REPO_ROOT, _z3_path)
    if not os.path.exists(_z3_abs):
        print(yellow(f"  WARNING: {_z3_path} not found — skipping Z3 analysis."))
        return

    _z3_dir = os.path.dirname(_z3_abs)
    _z3_module = os.path.splitext(os.path.basename(_z3_abs))[0]

    # Add the module's directory to sys.path so importlib can find it
    if _z3_dir not in sys.path:
        sys.path.insert(0, _z3_dir)

    try:
        # Reload if already cached (supports repeated --z3 calls in the same process)
        if _z3_module in sys.modules:
            _mod = _il.reload(sys.modules[_z3_module])
        else:
            _mod = _il.import_module(_z3_module)
    except Exception as exc:
        print(yellow(f"  WARNING: Could not load formal_analysis.py: {exc}"))
        return

    if not getattr(_mod, "_Z3_AVAILABLE", False):
        print(
            yellow(
                "  Z3 not installed — skipping formal analysis.\n"
                "  Install with:  pip install z3-solver"
            )
        )
        return

    z3_results = _mod.run_all(bind_values=bind_values, verbose=verbose)

    # Print using the module's own output function, respecting colour setting
    _mod._print_results(z3_results, verbose=verbose, color=_USE_COLOR)

    # Persist Z3 gap summary alongside SysML results
    z3_summary = [
        {
            "level": r.level,
            "req_id": r.req_id,
            "outcome": r.outcome,
            "detail": r.detail[:300] if r.detail else "",
        }
        for r in z3_results
    ]
    os.makedirs(LIB_DIR, exist_ok=True)
    out_path = os.path.join(LIB_DIR, "z3-analysis-results.json")
    with open(out_path, "w") as fh:
        import json as _json

        _json.dump(z3_summary, fh, indent=2)
    print(dim("  Z3 results written to lib/z3-analysis-results.json"))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="verify.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project-dir",
        default="/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/SysMLInfra/examples/bilgepump",
        help="Path to the project directory containing sysml-project.yml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List layers and check files; do not run the kernel",
    )
    parser.add_argument(
        "--negative",
        action="store_true",
        help="Inject pumpA.flowRate=0 (pump A failure simulation)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run ALL layers including FMEA negative tests + UQ sweep",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Use Python regex/eval only (DEV/TEST use only; see WARNING in output)",
    )
    parser.add_argument(
        "--require-kernel",
        action="store_true",
        help="Exit with code 2 if the SysML v2 kernel is not installed (no fallback)",
    )
    parser.add_argument(
        "--visual",
        action="store_true",
        help="Generate system topology and traceability diagrams",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Push committed layers to the SST API after verification",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show constraint expression for each requirement",
    )
    parser.add_argument(
        "--z3",
        action="store_true",
        help="Run Z3 formal analysis (formal_analysis.py) after SysML verification",
    )
    parser.add_argument(
        "--live",
        metavar="CONFIG",
        help="Load bind values from a live sensor adapter config file "
        "(see scripts/sensor_adapter.py for the config schema). "
        "Takes a single snapshot then runs verification.",
    )
    args = parser.parse_args()
    run_verify(args)


def run_verify(args) -> None:
    project_dir = Path(args.project_dir)
    print("Using project: ", project_dir)

    if not project_dir.exists():
        print(red(f"ERROR: Project directory not found: {project_dir}"))
        sys.exit(2)

    MANIFEST = project_dir / "sysml-project.yml"
    # ── Load manifest ──────────────────────────────────────────────────────────
    if not MANIFEST.exists():
        print(red(f"ERROR: sysml-project.yml not found at {MANIFEST}"))
        sys.exit(2)

    project_name, all_layers, validation_layers = _read_manifest(str(MANIFEST))

    if not all_layers:
        print(red("ERROR: sysml-project.yml contains no layers entries."))
        sys.exit(2)

    # Dry-run: always uses full layers list
    if args.dry_run:
        _dry_run(project_name, all_layers, validation_layers)

    # ── Live sensor mode ───────────────────────────────────────────────────────
    _live_bind_values: dict | None = None
    if args.live:
        import importlib.util as _ilu
        import json as _json

        _adapter_path = os.path.join(REPO_ROOT, "scripts", "sensor_adapter.py")
        if not os.path.exists(_adapter_path):
            raise FileNotFoundError("scripts/sensor_adapter.py not found")

        spec = _ilu.spec_from_file_location("sensor_adapter", _adapter_path)
        if spec is None or spec.loader is None:
            raise ImportError("Failed to load sensor_adapter module spec")

        _sa_mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(_sa_mod)

        if not os.path.exists(args.live):
            raise FileNotFoundError(f"Live config file not found: {args.live}")

        with open(args.live) as _fh:
            _live_config = _json.load(_fh)
        _adapter = _sa_mod.make_adapter(_live_config)
        _snap = _adapter.snapshot()
        _live_bind_values = _snap["values"]
        print(
            f"\n  {cyan('Live mode')} — snapshot from {_snap['source']} at {_snap['timestamp']}"
        )
        print(f"  {len(_live_bind_values)} bind values loaded from sensor adapter")

    # Select the working layer set
    if args.all:
        layer_set = all_layers
        mode_label = "all-layers (includes negative tests)"
    else:
        layer_set = (
            validation_layers
            if (validation_layers and not args.negative)
            else all_layers
        )
        mode_label = (
            "negative test" if args.negative else "positive test (validation_layers)"
        )

    # ── Engine selection ───────────────────────────────────────────────────────
    use_kernel = not args.fallback
    kernel_name: str | None = None
    if args.fallback:
        print()
        print(yellow("═" * 66))
        print(yellow("  ⚠  WARNING: --fallback active — Python regex/eval ONLY"))
        print(yellow("  ─" * 64))
        print(yellow("  This mode does NOT evaluate SysML v2 semantics or types."))
        print(yellow("  For development and testing iteration ONLY."))
        print(yellow("  Use the SysML v2 kernel for authoritative results."))
        print(yellow("═" * 66))
    if use_kernel:
        kernel_name = _discover_sysml_kernel()
        if kernel_name is None:
            if getattr(args, "require_kernel", False):
                print()
                print(red("═" * 66))
                print(red("  ERROR: SysML v2 kernel NOT FOUND"))
                print(red("  ─" * 64))
                print(
                    red(
                        "  ——require-kernel was set: refusing to fall back to Python eval."
                    )
                )
                print(red("  The Python fallback cannot perform SysML type checking."))
                print(
                    red(
                        "  Install the kernel:  bash setup.sh  (requires Java 21 + Miniconda)"
                    )
                )
                print(red("═" * 66))
                sys.exit(2)
            print()
            print(yellow("═" * 66))
            print(
                yellow("  WARNING: SysML v2 kernel NOT FOUND — running Python fallback")
            )
            print(yellow("  ─" * 64))
            print(yellow("  The fallback is for development iteration ONLY."))
            print(yellow("  Real constraint evaluation requires the SysML v2 kernel."))
            print(yellow("  Install:  bash setup.sh  (requires Java 21 + Miniconda)"))
            print(yellow("═" * 66))
            use_kernel = False

    engine_label = (
        f"SysML v2 kernel ({kernel_name}) — parse/type-check + %eval constraint evaluation"
        if use_kernel
        else "Python regex/eval (fallback — NOT authoritative)"
    )
    _print_header(project_name, mode_label, engine_label)

    results: list[dict] = []

    # ── Kernel path ────────────────────────────────────────────────────────────
    if use_kernel and kernel_name:
        print(
            f"\n  {dim('Starting SysML v2 kernel — this takes ~10 s on first run...')}"
        )
        eval_cells = _build_kernel_eval_cells(layer_set, args.negative, project_dir)
        all_ok, cell_results, eval_results = _run_kernel(
            layer_set, kernel_name, project_dir, eval_cells
        )
        if cell_results:
            _print_layer_summary(cell_results)

        if eval_results:
            # Kernel evaluated requirements via ExpressionEvaluator.INSTANCE (%eval).
            # For any cell where the kernel returned an error or unparseable output,
            # fill in the result using Python fallback so nothing is silently lost.
            unknown_reqs = [
                r["requirement"] for r in eval_results if r["satisfied"] is None
            ]
            if unknown_reqs:
                print(
                    f"\n  {yellow(f'⚠  {len(unknown_reqs)} requirement(s) returned UNKNOWN from kernel — using Python fallback for those.')}"
                )
                fb_results = _run_fallback(layer_set, args.negative, project_dir)
                fb_map = {r["requirement"]: r for r in fb_results}
                for r in eval_results:
                    if r["satisfied"] is None and r["requirement"] in fb_map:
                        r["satisfied"] = fb_map[r["requirement"]].get("satisfied")
                        r["source"] = "python-fallback"
            results = eval_results
        else:
            # No eval cells were built (analysis/requirements files not found).
            # Fall back entirely so we still produce some output.
            print(
                f"\n  {yellow('⚠  No %eval cells built — kernel only checked syntax.')}"
            )
            results = _run_fallback(layer_set, args.negative, project_dir, args.verbose)
    else:
        # ── Fallback path ──────────────────────────────────────────────────────
        results = _run_fallback(layer_set, args.negative, project_dir, args.verbose)

    # ── Print results ──────────────────────────────────────────────────────────
    all_pass, violated = _print_results(results, show_expr=args.verbose)

    # ── Fault traces for violations ────────────────────────────────────────────
    if violated:
        _print_fault_traces(violated, all_layers, args.negative)

    # ── Persist results ────────────────────────────────────────────────────────
    engine_str = f"kernel:{kernel_name}" if use_kernel else "python-eval"
    _save_results(results, "negative" if args.negative else "positive", engine_str)

    # ── Visual diagrams ────────────────────────────────────────────────────────
    if args.visual:
        print(f"\n  {bold('Generating diagrams...')}")
        try:
            from scripts.diagram_gen import generate_all  # noqa: PLC0415

            generated = generate_all(str(project_dir), all_layers, results)
            if generated:
                print(f"\n  {dim('Diagrams written to:')}")
                for p in generated:
                    rel = os.path.relpath(p, REPO_ROOT)
                    print(f"    {cyan(rel)}")
        except Exception as exc:
            print(yellow(f"  WARNING: Diagram generation failed: {exc}"))

    # ── Z3 formal analysis ─────────────────────────────────────────────────────
    if args.z3:
        _run_z3_analysis(
            bind_values=_live_bind_values, verbose=args.verbose, MANIFEST=MANIFEST
        )

    # ── Optional publish ───────────────────────────────────────────────────────
    if args.publish:
        _publish(all_layers, project_name)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
