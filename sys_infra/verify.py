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
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from scripts.utils import dry_runner
from sys_infra.api_utils import (
    create_project,
    delete_project_by_name,
    get_project_by_name,
)
from sys_infra.commit import check_api_server, get_host
from sys_infra.environment import LIB_DIR, REPO_ROOT, SysandPackageStructure
from sys_infra.utils import _USE_COLOR, bold, cyan, dim, green, red, yellow


# ── Manifest reader (same logic as ci_kernel_validate.py) ────────────────────


def _read_manifest(path: str) -> tuple[str, list[str], list[str] | None]:
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

    # TODO Is this necessary? Can`t we just run all these files and it should be good?

    analysis_path = (
        layer_paths  # next((p for p in layer_paths if "analysis" in p.lower()), None)
    )
    requirements_path = layer_paths  # next(
    #    (p for p in layer_paths if "requirements" in p.lower()), None
    # )
    safety_path = (
        layer_paths  # next((p for p in layer_paths if "safety" in p.lower()), None)
    )

    if not analysis_path or not requirements_path:
        print(
            red(
                "ERROR: Cannot locate Analysis.sysml or Requirements.sysml in layer list."
            )
        )
        sys.exit(2)

    # analysis_text = _strip_comments(_read(os.path.join(project_dir, analysis_path)))

    analysis_text = "\n".join(
        _strip_comments(_read(os.path.join(project_dir, p))) for p in analysis_path
    )

    bind_values, bare_values = _build_bind_values(analysis_text, negative)

    # Collect requirement defs from Requirements.sysml + Safety.sysml
    req_texts: list[tuple[str, str]] = []  # (rel_path, content)
    for rp in set(requirements_path + safety_path):
        # if rp and os.path.exists(os.path.join(project_dir, rp)):
        req_texts.append((rp, _strip_comments(_read(os.path.join(project_dir, rp)))))

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


# ── Option B: verify against the PUBLISHED model (sysml_assertions table) ─────
#
# The model no longer carries ``bind path = value;`` statements (the old text-
# commit pipeline). Verification verdicts now come from computed Boolean
# attributes that the SysML v2 kernel evaluates during publish; the pipeline
# (mons_wp1/materialize_sysml_values.py) stores those kernel verdicts in the
# ``sysml_assertions`` table of the local sysml2 database. ``--published`` reads
# those authoritative verdicts instead of re-deriving them by regex/eval — so
# verify.py keeps working without any bind statements to parse.

_DB = dict(
    host=os.environ.get("SYSML_DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("SYSML_DB_PORT", "5432")),
    dbname=os.environ.get("SYSML_DB_NAME", "sysml2"),
    user=os.environ.get("SYSML_DB_USER", "postgres"),
    password=os.environ.get("SYSML_DB_PASSWORD", "mysecretpassword"),
)


def _run_published(negative: bool, want_all: bool) -> list[dict]:
    """Read kernel-evaluated verdicts from the published ``sysml_assertions``
    table and return them in the standard result-dict shape.

    Filtering mirrors the kernel/fallback modes:
        default     -> positive functional checks (kind='positive')
        --negative  -> fault-injection checks (kind='negative')
        --all       -> every assertion (positive + negative + UQ)
    """
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError:
        print(red("ERROR: psycopg2 not installed — cannot read published assertions."))
        print("  Install CI dependencies:  (cd SysMLInfra && uv sync)")
        sys.exit(2)

    try:
        conn = psycopg2.connect(**_DB)
    except Exception as exc:
        print(red(f"ERROR: cannot connect to sysml2 database ({exc})."))
        print("  Is the stack up? Publish first: mons_wp1/publish_bilgepump.sh")
        sys.exit(2)

    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.sysml_assertions')")
            if cur.fetchone()[0] is None:
                print(red("ERROR: sysml_assertions table not found."))
                print(
                    "  Build it: mons_wp1/publish_bilgepump.sh  (publish + materialize)"
                )
                sys.exit(2)
            sql = (
                "SELECT assertion, requirement, kind, expected, result_bool, "
                "status, note FROM sysml_assertions"
            )
            if want_all:
                params: tuple = ()
            elif negative:
                sql += " WHERE kind = %s"
                params = ("negative",)
            else:
                sql += " WHERE kind = %s"
                params = ("positive",)
            sql += " ORDER BY layer, assertion"
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    results: list[dict] = []
    for assertion, requirement, kind, expected, result_bool, status, note in rows:
        results.append(
            {
                "requirement": assertion,
                # ``satisfied`` reflects the kernel's actual verdict so the
                # SATISFIED/VIOLATED display and exit code stay meaningful;
                # negative (fault) checks are VIOLATED by design.
                "satisfied": result_bool,
                "expr": f"{requirement} [{kind}, expected={expected}, {status}]",
                "label": note or assertion,
                "source": "published:sysml_assertions",
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
    """
    analysis_path = (
        layer_paths  # next((p for p in layer_paths if "analysis" in p.lower()), None)
    )
    requirements_path = layer_paths  # next(
    #    (p for p in layer_paths if "requirements" in p.lower()), None
    # )
    safety_path = (
        layer_paths  # next((p for p in layer_paths if "safety" in p.lower()), None)
    )

    if not analysis_path or not requirements_path:
        print(
            red(
                "ERROR: Cannot locate Analysis.sysml or Requirements.sysml in layer list."
            )
        )
        sys.exit(2)

    # analysis_text = _strip_comments(_read(os.path.join(project_dir, analysis_path)))

    analysis_text = "\n".join(
        _strip_comments(_read(os.path.join(project_dir, p))) for p in analysis_path
    )

    bind_values, bare_values = _build_bind_values(analysis_text, negative)

    # Collect requirement defs from Requirements.sysml + Safety.sysml
    req_texts: list[tuple[str, str]] = []  # (rel_path, content)
    for rp in set(requirements_path + safety_path):
        # if rp and os.path.exists(os.path.join(project_dir, rp)):
        req_texts.append(
            (str(project_dir / rp), _strip_comments(_read(str(project_dir / rp))))
        )

    req_pattern = re.compile(
        r"requirement\s+def\s+(\w+).*?require\s+constraint\s*\{([^}]+)\}",
        re.DOTALL,
    )

    eval_cells: list[tuple[str, str, str]] = []
    for _, text in req_texts:
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
        resources={"metadata": {"path": project_dir}},
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
    elif sources == {"published:sysml_assertions"}:
        section_label = (
            "Requirement evaluation  [engine: published kernel %eval verdicts]"
        )
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


def _publish(layer_paths: list[str], project_name: str, project_dir: Path) -> None:
    """Upload model layers to the SST public API (optional, for sharing)."""
    try:
        import requests  # noqa: PLC0415
    except ImportError:
        print(
            yellow("  SKIPPED: requests library not installed (pip install requests)")
        )
        return

    api_base = os.environ.get("SYSML_API_BASE")
    if api_base is None:
        raise ValueError("Set SYSML_API_BASE in .env file")
    print(f"\n  {bold('Publishing to SST API:')}  {api_base}")

    try:
        r = requests.get(f"{api_base}/projects", timeout=8000)
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

    response = create_project(api_base=api_base, project_name=project_name)
    if isinstance(response, int):
        print(red(f"  ERROR: Failed to create project (HTTP {r.status_code})"))
        raise ConnectionAbortedError(
            f"  ERROR: Failed to create project (HTTP {r.status_code})"
        )

    project_id = response.get("@id") or r.json().get("id")

    print(f"  Project ID : {project_id}")

    commit_ids: dict[str, str] = {}
    # TODO Can we join all bodies into a single commit.
    # Would there be dependency issues if doing this?
    for layer_file in layer_paths:
        abs_path = os.path.join(project_dir, layer_file)
        body = _read(abs_path)
        stem = Path(layer_file).stem.lower()
        rc = requests.post(
            f"{api_base}/projects/{project_id}/commits",
            json={
                "description": stem,
                "changes": [{"@type": "TextualRepresentation", "body": body}],
            },
            timeout=3000,
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


def _run_kernel_publish(
    layer_paths: list[str], kernel_name: str, project_dir: Path, project_name: str
) -> tuple[bool, list[Any]]:
    """
    Publishes the layers bundled as one "superpackage". This is how the same project can be used.
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
    n_model_cells = 3
    all_packages = []
    package_name = f"{project_name}Super"
    super_package_prefix = f"package {package_name} {{\n\n"
    super_package_suffix = "\n }"
    super_text = super_package_prefix

    for layer_file in layer_paths:
        abs_path = os.path.join(project_dir, layer_file)

        text = _read(abs_path)
        super_text += text
        pattern = r"package\s+'?([\w:]+)'?\s*\{"
        packages = re.findall(pattern, text)
        all_packages += packages
    super_text += super_package_suffix

    nb.cells.append(nbformat.v4.new_code_cell(super_text))

    repo_cell = nbformat.v4.new_code_cell(f"%repo {get_host()}")
    publish_cell = nbformat.v4.new_code_cell(
        f"%publish {package_name} --project='{package_name}_project'"
    )
    publish_cell.metadata["tags"] = ["raises-exception"]
    nb.cells.append(repo_cell)
    nb.cells.append(publish_cell)

    client = NotebookClient(
        nb,
        timeout=300,
        kernel_name=kernel_name,
        resources={"metadata": {"path": project_dir}},
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
        return False, []

    # ── Parse model layer results ─────────────────────────────────────────────
    cell_results: list[dict] = []
    all_ok = True
    for i in range(n_model_cells):
        cell = nb.cells[i]
        errors = [o for o in cell.get("outputs", []) if o.get("output_type") == "error"]
        cell_results.append(
            {
                "ok": not errors,
                "errors": errors,
            }
        )
        if errors:
            all_ok = False

    return all_ok, cell_results


""" def _dry_run(
    name: str, layers: list, project_dir: str, validation_layers: list | None
) -> None:
    # TODO the function dry_runner in ci_kernel_validate.py has some (if not all) 
    # overlapping logic with this function; consider refactoring to reuse code

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
        path = os.path.join(project_dir, fname)
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
    sys.exit(0) """


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


def run_verify(
    project_dir: Path,
    dry_run,
    negative,
    all,
    fallback,
    require_kernel,
    visual,
    publish,
    z3,
    live,
    verbose,
    published=False,
) -> None:
    print("Using project: ", project_dir)

    if not project_dir.exists():
        print(red(f"ERROR: Project directory not found: {project_dir}"))
        sys.exit(2)

    MANIFEST = project_dir / "sysml-project.yml"
    validation_layers: list[str] | None
    # ── Load manifest or fallback ───────────────────────────────────────────────
    if not MANIFEST.exists():
        sysandpackage = SysandPackageStructure(project_dir)
        print(f"WARNING: sysml-project.yml not found at {MANIFEST}")
        print("Falling back to reading .sysml files in project_dir")

        # Collect all .sysml files
        sysml_files = sorted(sysandpackage.project_dir.glob("*.sysml"))

        if not sysml_files:
            print("ERROR: No .sysml files found in project directory")
            sys.exit(2)

        # Use filenames (or full paths depending on your needs)
        all_layers = [str(f) for f in sysml_files]
        validation_layers = list(all_layers)

        # Derive a project name (optional)
        project_name = sysandpackage.project_name

    else:
        project_name, all_layers, validation_layers = _read_manifest(str(MANIFEST))

    if not all_layers:
        print(red("ERROR: sysml-project.yml contains no layers entries."))
        sys.exit(2)

    # Dry-run: always uses full layers list
    if dry_run:
        dry_runner(project_name, all_layers, project_dir, validation_layers)

    # ── Option B: verify against the published model (sysml_assertions) ────────
    results: list[dict] = []
    if published:
        mode_label = (
            "all assertions"
            if all
            else ("negative (fault injections)" if negative else "positive functional")
        )
        _print_header(
            project_name,
            mode_label,
            "Published model — kernel %eval verdicts (sysml_assertions table)",
        )
        results = _run_published(negative, all)
        if not results:
            print(
                yellow("\n  No matching assertions in sysml_assertions for this mode.")
            )
            print(dim("  Publish first: mons_wp1/publish_bilgepump.sh"))
            sys.exit(2)
        all_pass, violated = _print_results(results, show_expr=verbose)
        _save_results(
            results,
            "negative" if negative else "positive",
            "published:sysml_assertions",
        )
        sys.exit(0 if all_pass else 1)

    # ── Live sensor mode ───────────────────────────────────────────────────────
    _live_bind_values: dict | None = None
    if live:
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

        if not os.path.exists(live):
            raise FileNotFoundError(f"Live config file not found: {live}")

        with open(live) as _fh:
            _live_config = _json.load(_fh)
        _adapter = _sa_mod.make_adapter(_live_config)
        _snap = _adapter.snapshot()
        _live_bind_values = _snap["values"]
        print(
            f"\n  {cyan('Live mode')} — snapshot from {_snap['source']} at {_snap['timestamp']}"
        )
        print(f"  {len(_live_bind_values)} bind values loaded from sensor adapter")

    # Select the working layer set
    if all:
        layer_set = all_layers
        mode_label = "all-layers (includes negative tests)"
    else:
        layer_set = (
            validation_layers if (validation_layers and not negative) else all_layers
        )
        mode_label = (
            "negative test" if negative else "positive test (validation_layers)"
        )

    # ── Engine selection ───────────────────────────────────────────────────────
    use_kernel = not fallback
    kernel_name: str | None = None
    if fallback:
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
            if require_kernel is False:
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

    results = []

    # ── Kernel path ────────────────────────────────────────────────────────────
    if use_kernel and kernel_name:
        print(
            f"\n  {dim('Starting SysML v2 kernel — this takes ~10 s on first run...')}"
        )
        eval_cells = _build_kernel_eval_cells(layer_set, negative, project_dir)
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
                fb_results = _run_fallback(layer_set, negative, project_dir)
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
            results = _run_fallback(layer_set, negative, project_dir, verbose)
    else:
        # ── Fallback path ──────────────────────────────────────────────────────
        results = _run_fallback(layer_set, negative, project_dir, verbose)

    # ── Print results ──────────────────────────────────────────────────────────
    all_pass, violated = _print_results(results, show_expr=verbose)

    # ── Fault traces for violations ────────────────────────────────────────────
    if violated:
        _print_fault_traces(violated, all_layers, negative)

    # ── Persist results ────────────────────────────────────────────────────────
    engine_str = f"kernel:{kernel_name}" if use_kernel else "python-eval"
    _save_results(results, "negative" if negative else "positive", engine_str)

    # ── Visual diagrams ────────────────────────────────────────────────────────
    if visual:
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
    if z3:
        _run_z3_analysis(
            bind_values=_live_bind_values, verbose=verbose, MANIFEST=MANIFEST
        )

    # ── Optional publish ───────────────────────────────────────────────────────
    if publish and kernel_name is not None:
        _run_kernel_publish(all_layers, kernel_name, project_dir, project_name)
        # _publish(all_layers, project_name, project_dir)

    sys.exit(0 if all_pass else 1)


# ── Publish entry point (sysml publish) ───────────────────────────────────────


def _resolve_version() -> str:
    """Model version string: GIT_SHA env, else the consumer repo's short HEAD."""
    import subprocess  # noqa: PLC0415

    sha = os.environ.get("GIT_SHA")
    if sha:
        return sha
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _record_published_version(api_project_name: str, version: str) -> None:
    """Persist the published version and best-effort set it on the API project."""
    import datetime  # noqa: PLC0415

    os.makedirs(LIB_DIR, exist_ok=True)
    record = {
        "project": api_project_name,
        "version": version,
        "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    out_path = os.path.join(LIB_DIR, "published-version.json")
    with open(out_path, "w") as fh:
        json.dump(record, fh, indent=2)
    print(f"  {dim('Version recorded in lib/published-version.json')}")

    # Best-effort: also stamp the version onto the API project description. Some
    # pilot API builds do not support updating a project, so failure is non-fatal.
    try:
        import requests  # noqa: PLC0415

        proj = get_project_by_name(api_project_name)
        if proj is not None:
            requests.put(
                f"{get_host()}/projects/{proj['@id']}",
                json={
                    "@type": "Project",
                    "name": api_project_name,
                    "description": f"version: {version}",
                },
                timeout=30,
            )
    except Exception as exc:
        print(dim(f"  (Could not set project description on API: {exc})"))


def run_publish(
    project_dir: Path,
    force: bool = False,
    version: str | None = None,
    verbose: bool = False,
) -> None:
    """Publish the model to the local SysML v2 API as ONE versioned project.

    Pythonises mons_wp1's publish_bilgepump.sh: reuses the API server check
    (sys_infra.commit.check_api_server) and the unified umbrella-publish notebook
    generator (sys_infra.publish_notebook). The whole model is published under a
    single STABLE project name (the manifest ``publish_root``), and one tagged
    ``%eval`` cell per assertion is executed so the materializer can build the
    ``sysml_assertions`` table.

    Versioning policy: the project carries a single version (a git SHA by
    default); republishing with --force deletes the previous project of the same
    name rather than accumulating versions.
    """
    from sys_infra.publish_notebook import build_publish_notebook

    print("Using project: ", project_dir)
    if not project_dir.exists():
        print(red(f"ERROR: Project directory not found: {project_dir}"))
        sys.exit(2)

    # 1. API must be reachable.
    check_api_server()

    # 2. Manifest must exist (layers/publish_root resolved by the generator).
    manifest = project_dir / "sysml-project.yml"
    if not manifest.exists():
        print(red(f"ERROR: sysml-project.yml not found at {manifest}"))
        sys.exit(2)

    # 3. Kernel is required to publish (no Python fallback for publishing).
    kernel_name = _discover_sysml_kernel()
    if kernel_name is None:
        print(red("ERROR: SysML v2 kernel not found — cannot publish."))
        print(dim("  Install it with setup.sh, then retry."))
        sys.exit(2)

    # 4. Version string (explicit --version wins).
    version = version or _resolve_version()

    # 5. Build the unified publish notebook (umbrella package + %eval cells).
    try:
        nb, publish_root = build_publish_notebook(
            project_dir, kernel_name, version=version
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(red(f"ERROR: could not build the publish notebook: {exc}"))
        sys.exit(2)

    # 6. Idempotency + delete-previous (keep only the latest version).
    existing = get_project_by_name(publish_root)
    if existing is not None:
        if not force:
            print(
                green(f"\n  Already published as '{publish_root}'. ")
                + dim("Use --force to republish.")
            )
            sys.exit(0)
        print(
            yellow(
                f"\n  --force: deleting previous project '{publish_root}' "
                f"(ID {existing['@id']}) before republishing."
            )
        )
        delete_project_by_name(publish_root)

    # 7. Execute the notebook headlessly: publish + evaluate every assertion.
    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import CellExecutionError
    except ImportError as exc:
        print(red(f"ERROR: {exc}"))
        print("  Install CI dependencies:  pip install nbclient nbformat")
        sys.exit(2)

    out_path = project_dir / "publish.ipynb"
    print(f"\n  {bold('Publishing model version:')} {version} → project '{publish_root}'")
    try:
        NotebookClient(nb, timeout=600, kernel_name=kernel_name).execute()
    except CellExecutionError as exc:
        nbformat.write(nb, str(out_path))
        print(red(f"\n  Publish FAILED — kernel error while executing publish.ipynb:\n{exc}"))
        sys.exit(1)

    # Persist the executed notebook so materialize_sysml_values.py can read the
    # tagged %eval outputs into the sysml_assertions table.
    nbformat.write(nb, str(out_path))

    # 8. Record the published version (+ best-effort API description stamp).
    _record_published_version(publish_root, version)

    print(green(f"\n  ✓ Published '{publish_root}' (version {version})."))
    sys.exit(0)


if __name__ == "__main__":
    ...
