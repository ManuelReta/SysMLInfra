"""
fault_tracer.py — Cross-layer fault localizer for the SysML v2 verification engine.

Parses all .sysml model files using regex to build a cross-layer index:
  - Requirements + Analysis → constraint expressions, bind values, file:line
  - Safety.sysml            → UCA annotations (ucaId, guideword, hazardRefs, failureModeLink)
  - FMEA.sysml              → FailureMode annotations (fmId, S, O, D, RPN, stateRef)

On a VIOLATED requirement, produces a full safety stack trace:
  requirement → failing bind value (file:line) → UCA (guideword, hazardRefs) → FMEA failure mode (RPN)

This module is pure Python (stdlib + regex only — no NetworkX, no Z3).
Imported by verify.py; also usable standalone.
"""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_comments(text: str) -> str:
    """Remove // line comments and /* */ block comments."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _read(path: str | Path) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _line_of(text: str, char_pos: int) -> int:
    """Return 1-based line number of a character position in text."""
    return text[:char_pos].count("\n") + 1


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------


def build_bind_index(
    layer_paths: list[str], repo_root: str, negative: bool = False
) -> dict:
    """
    Parse all 'bind' statements from the given layer files.

    Returns:
        {
          "full.path.attr": {
              "value": <float|bool|str>,
              "file":  "examples/<project>/Analysis.sysml",
              "line":  42,
          },
          ...
        }
    """
    index: dict[str, dict] = {}
    for rel_path in layer_paths:
        abs_path = os.path.join(repo_root, rel_path)
        if not os.path.exists(abs_path):
            continue
        raw = _read(abs_path)
        clean = _strip_comments(raw)
        for m in re.finditer(r"\bbind\s+([\w.]+)\s*=\s*([^;]+);", clean):
            attr_path = m.group(1).strip()
            raw_value = m.group(2).strip()
            line_no = _line_of(clean, m.start())
            if raw_value.lower() == "true":
                value: Any = True
            elif raw_value.lower() == "false":
                value = False
            else:
                try:
                    value = float(raw_value)
                except ValueError:
                    value = raw_value  # keep as string (e.g. bind references)
            index[attr_path] = {
                "value": value,
                "file": rel_path,
                "line": line_no,
            }

    # Negative test override
    if negative:
        for key in list(index.keys()):
            if "pumpa" in key.lower() and "flowrate" in key.lower():
                index[key] = {
                    "value": 0.0,
                    "file": "[negative-test override]",
                    "line": 0,
                }
    return index


def build_uca_index(safety_path: str, repo_root: str) -> dict:
    """
    Parse #UCA { ... } annotation blocks from Safety.sysml.

    Returns:
        {
          "UCA-001": {
              "ucaId":           "UCA-001",
              "controlAction":   "ActivatePumpA",
              "guideword":       "Not Provided",
              "context":         "...",
              "hazardRefs":      "H-1,HS-1",
              "failureModeLink": "FM-C-001",
              "transitionRef":   "MONITORING_to_PUMP_A_ACTIVE",
              "file":            "examples/<project>/Safety.sysml",
              "line":            118,
          },
          ...
        }
    """
    abs_path = os.path.join(repo_root, safety_path)
    if not os.path.exists(abs_path):
        return {}
    raw = _read(abs_path)
    clean = _strip_comments(raw)
    index: dict[str, dict] = {}

    # Match each #UCA { ... } block
    for block_m in re.finditer(r"#UCA\s*\{([^}]+)\}", clean, re.DOTALL):
        block_text = block_m.group(1)
        line_no = _line_of(clean, block_m.start())
        entry: dict[str, Any] = {"file": safety_path, "line": line_no}
        for field in (
            "ucaId",
            "controlAction",
            "guideword",
            "context",
            "hazardRefs",
            "severity",
            "failureModeLink",
            "transitionRef",
            "sourceDoc",
            "section",
        ):
            fm = re.search(rf'{field}\s*=\s*"([^"]*)"', block_text)
            if fm:
                entry[field] = fm.group(1)
        uid = entry.get("ucaId", "")
        if uid:
            index[uid] = entry

    return index


def build_fmea_index(fmea_path: str, repo_root: str) -> dict:
    """
    Parse #FailureMode { ... } annotation blocks from FMEA.sysml.

    Returns:
        {
          "FM-PA-002": {
              "fmId":            "FM-PA-002",
              "component":       "<ComponentPartDef>",
              "instance":        "pumpA",
              "failureModeText": "...",
              "failureEffect":   "...",
              "severity":        7,
              "occurrence":      5,
              "detection":       6,
              "rpn":             210,
              "ucaRef":          "",
              "hazardRef":       "H-1",
              "stateRef":        "PUMP_A_ACTIVE",
              "file":            "examples/<project>/FMEA.sysml",
              "line":            195,
          },
          ...
        }
    """
    abs_path = os.path.join(repo_root, fmea_path)
    if not os.path.exists(abs_path):
        return {}
    raw = _read(abs_path)
    clean = _strip_comments(raw)
    index: dict[str, dict] = {}

    for block_m in re.finditer(r"#FailureMode\s*\{([^}]+)\}", clean, re.DOTALL):
        block_text = block_m.group(1)
        line_no = _line_of(clean, block_m.start())
        entry: dict[str, Any] = {"file": fmea_path, "line": line_no}

        # String fields
        for field in (
            "fmId",
            "component",
            "instance",
            "failureModeText",
            "failureEffect",
            "ucaRef",
            "hazardRef",
            "stateRef",
            "sourceDoc",
            "section",
        ):
            fm = re.search(rf'{field}\s*=\s*"([^"]*)"', block_text)
            if fm:
                entry[field] = fm.group(1)

        # Numeric fields
        for field in ("severity", "occurrence", "detection", "rpn"):
            fm = re.search(rf"{field}\s*=\s*([0-9]+(?:\.[0-9]+)?)", block_text)
            if fm:
                try:
                    entry[field] = int(fm.group(1))
                except ValueError:
                    entry[field] = float(fm.group(1))

        uid = entry.get("fmId", "")
        if uid:
            index[uid] = entry

    return index


def build_requirement_index(req_paths: list[str], repo_root: str) -> dict:
    """
    Parse requirement def blocks from Requirements.sysml and Safety.sysml.

    Returns:
        {
          "WaterLevelRequirement": {
              "expr":    "sys.sensor.waterLevel <= 0.3",
              "file":    "examples/<project>/Requirements.sysml",
              "line":    45,
              "reg_ids": ["BPS-REQ-001"],
          },
          ...
        }
    """
    index: dict[str, dict] = {}
    reg_id_re = re.compile(r"(BPS-REQ-\d+|UCA-\d+-SR-\d+|SR-\d+)")

    for rel_path in req_paths:
        abs_path = os.path.join(repo_root, rel_path)
        if not os.path.exists(abs_path):
            continue
        raw = _read(abs_path)
        clean = _strip_comments(raw)

        for m in re.finditer(
            r"requirement\s+def\s+(\w+)\s*(?:\{[^{]*?require\s+constraint\s*\{([^}]+)\})",
            clean,
            re.DOTALL,
        ):
            name = m.group(1)
            expr = m.group(2).strip().replace("\n", " ")
            expr = re.sub(r"\s+", " ", expr)
            line_no = _line_of(clean, m.start())

            # Collect any BPS-REQ-xxx IDs appearing near the requirement def
            context_window = clean[max(0, m.start() - 300) : m.start() + 200]
            reg_ids = reg_id_re.findall(context_window)

            index[name] = {
                "expr": expr,
                "file": rel_path,
                "line": line_no,
                "reg_ids": list(dict.fromkeys(reg_ids)),  # deduplicate, keep order
            }
    return index


# ---------------------------------------------------------------------------
# Linkage: connect a failing requirement to UCAs and FMEA failure modes
# ---------------------------------------------------------------------------


def _extract_component_names(req_expr: str) -> list[str]:
    """
    Extract component instance names from a require constraint expression.
    e.g. "sys.sensor.waterLevel <= 0.3" → ["sensor"]
         "(sys.pumpA.flowRate + sys.pumpB.flowRate) >= designInflow" → ["pumpA", "pumpB"]
    """
    # Match sys.<component>.<attribute>
    hits = re.findall(r"sys\.(\w+)\.", req_expr)
    return list(dict.fromkeys(hits))


def _find_ucas_for_component(
    component_names: list[str],
    uca_index: dict,
) -> list[dict]:
    """Return UCAs whose controlAction or failureModeLink mentions any component."""
    results: list = []
    for comp in component_names:
        comp_lower = comp.lower()
        for uid, uca in uca_index.items():
            ca = uca.get("controlAction", "").lower()
            fm_link = uca.get("failureModeLink", "").lower()
            # Match by component name appearing in controlAction or failureModeLink
            # Also match by instance name in context (e.g. "pumpA" → "Pump")
            short = re.sub(
                r"[A-Z]", lambda x: x.group().lower(), comp
            )  # camelCase → lower
            if (
                comp_lower in ca
                or comp_lower in fm_link
                or short in ca
                or short in fm_link
                or comp.lower().replace("pump", "") in ca.lower()
            ):
                if uid not in [r["ucaId"] for r in results]:
                    results.append(uca)
    return results


def _find_fmea_for_ucas(ucas: list[dict], fmea_index: dict) -> list[dict]:
    """Return FMEA failure modes linked to the given UCAs."""
    results = []
    uca_ids = {u.get("ucaId", "") for u in ucas}
    fm_links = {u.get("failureModeLink", "") for u in ucas}

    for fmid, fm in fmea_index.items():
        uca_ref = fm.get("ucaRef", "")
        if uca_ref in uca_ids or fmid in fm_links:
            results.append(fm)
    return results


def _find_bind_for_expr(
    expr: str,
    bind_index: dict,
) -> list[dict]:
    """Find bind entries whose attribute path appears in the requirement expression."""
    hits = []
    for attr_path, info in bind_index.items():
        bare = attr_path.rsplit(".", 1)[-1]
        # Check if the attribute bare name or full path is referenced in the expr
        if bare in expr or attr_path in expr:
            hits.append({"path": attr_path, **info})
    # Sort by path length descending to show most specific first
    hits.sort(key=lambda x: -len(x["path"]))
    return hits


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class FaultTrace:
    """
    Holds a full safety trace for one violated requirement.

    Attributes:
        req_name:    SysML requirement def name
        reg_ids:     List of regulatory IDs (BPS-REQ-xxx)
        expr:        The constraint expression that evaluated to False
        req_file:    Source file of the requirement def
        req_line:    Line number of the requirement def
        bind_hits:   List of relevant bind entries with file:line
        ucas:        List of linked UCA entries
        fmea_modes:  List of linked FMEA failure mode entries
    """

    def __init__(
        self,
        req_name: str,
        reg_ids: list[str],
        expr: str,
        req_file: str,
        req_line: int,
        bind_hits: list[dict],
        ucas: list[dict],
        fmea_modes: list[dict],
    ):
        self.req_name = req_name
        self.reg_ids = reg_ids
        self.expr = expr
        self.req_file = req_file
        self.req_line = req_line
        self.bind_hits = bind_hits
        self.ucas = ucas
        self.fmea_modes = fmea_modes

    def format(self, color: bool = True) -> str:
        RED = "\033[31m" if color else ""
        YELLOW = "\033[33m" if color else ""
        CYAN = "\033[36m" if color else ""
        RESET = "\033[0m" if color else ""
        BOLD = "\033[1m" if color else ""

        _ = f"[{', '.join(self.reg_ids)}]" if self.reg_ids else ""
        lines = [
            f"  {RED}{BOLD}Constraint{RESET} : {self.expr}",
            f"  {CYAN}Defined at{RESET}  : {self.req_file}:{self.req_line}",
        ]

        if self.bind_hits:
            lines.append(f"  {YELLOW}Bind values{RESET} :")
            for b in self.bind_hits:
                marker = (
                    "  ◀ FAULT"
                    if b["value"] == 0.0 and "flow" in b["path"].lower()
                    else ""
                )
                lines.append(
                    f"    {b['path']} = {b['value']}  [{b['file']}:{b['line']}]{marker}"
                )
        else:
            lines.append(
                f"  {YELLOW}Bind values{RESET} : (no direct bind found — check Analysis.sysml)"
            )

        if self.ucas:
            lines.append(f"  {YELLOW}UCA trace{RESET}   :")
            for u in self.ucas:
                lines.append(
                    f"    {u.get('ucaId', '?')} — {u.get('controlAction', '?')} "
                    f"({u.get('guideword', '?')})  "
                    f"→ hazards: {u.get('hazardRefs', '?')}  "
                    f"[{u.get('file', '?')}:{u.get('line', '?')}]"
                )
                if u.get("transitionRef"):
                    lines.append(f"      state transition: {u['transitionRef']}")
        else:
            lines.append(
                f"  {YELLOW}UCA trace{RESET}   : (no UCA linked to this component)"
            )

        if self.fmea_modes:
            lines.append(f"  {YELLOW}FMEA trace{RESET}  :")
            for fm in self.fmea_modes:
                s = fm.get("severity", "?")
                o = fm.get("occurrence", "?")
                d = fm.get("detection", "?")
                r = fm.get("rpn", "?")
                lines.append(
                    f"    {fm.get('fmId', '?')} — {fm.get('failureModeText', '?')}"
                )
                lines.append(
                    f"      Component: {fm.get('component', '?')} ({fm.get('instance', '?')})"
                )
                lines.append(
                    f"      S={s} O={o} D={d}  RPN={r}"
                    + (f"  stateRef: {fm['stateRef']}" if fm.get("stateRef") else "")
                )
                lines.append(f"      Effect: {fm.get('failureEffect', '?')}")
                lines.append(f"      [{fm.get('file', '?')}:{fm.get('line', '?')}]")
        else:
            lines.append(
                f"  {YELLOW}FMEA trace{RESET}  : (no FMEA failure mode linked)"
            )

        return "\n".join(lines)


class FaultTracer:
    """
    Cross-layer fault localizer.

    Usage:
        tracer = FaultTracer(repo_root, layer_paths)
        tracer.load()
        traces = tracer.trace_violations(violation_names)
        for t in traces:
            print(t.format())
    """

    def __init__(
        self, repo_root: str, all_layer_paths: list[str], negative: bool = False
    ):
        self.repo_root = repo_root
        self.layer_paths = all_layer_paths
        self.negative = negative
        self._bind_index: dict = {}
        self._req_index: dict = {}
        self._uca_index: dict = {}
        self._fmea_index: dict = {}

    def load(self) -> None:
        """Parse all layer files and build internal indices."""
        self._bind_index = build_bind_index(
            self.layer_paths, self.repo_root, self.negative
        )

        # Requirement index — scan all layers (requirements appear in both Requirements.sysml and Safety.sysml)
        self._req_index = build_requirement_index(self.layer_paths, self.repo_root)

        # Safety UCA index
        safety_layers = [p for p in self.layer_paths if "safety" in p.lower()]
        for sl in safety_layers:
            self._uca_index.update(build_uca_index(sl, self.repo_root))

        # FMEA failure mode index
        fmea_layers = [p for p in self.layer_paths if "fmea" in p.lower()]
        for fl in fmea_layers:
            self._fmea_index.update(build_fmea_index(fl, self.repo_root))

    def trace_violations(self, violated_req_names: list[str]) -> list[FaultTrace]:
        """
        For each violated requirement name, build a full FaultTrace.

        Args:
            violated_req_names: list of SysML requirement def names that evaluated to VIOLATED.

        Returns:
            List of FaultTrace objects, one per violated requirement.
        """
        traces = []
        for req_name in violated_req_names:
            req_info = self._req_index.get(req_name)
            if req_info is None:
                # Build a minimal stub trace
                traces.append(
                    FaultTrace(
                        req_name=req_name,
                        reg_ids=[],
                        expr="(constraint not found in parsed layers)",
                        req_file="?",
                        req_line=0,
                        bind_hits=[],
                        ucas=[],
                        fmea_modes=[],
                    )
                )
                continue

            expr = req_info["expr"]
            components = _extract_component_names(expr)
            bind_hits = _find_bind_for_expr(expr, self._bind_index)
            ucas = _find_ucas_for_component(components, self._uca_index)
            fmea_modes = _find_fmea_for_ucas(ucas, self._fmea_index)

            traces.append(
                FaultTrace(
                    req_name=req_name,
                    reg_ids=req_info.get("reg_ids", []),
                    expr=expr,
                    req_file=req_info["file"],
                    req_line=req_info["line"],
                    bind_hits=bind_hits,
                    ucas=ucas,
                    fmea_modes=fmea_modes,
                )
            )
        return traces
