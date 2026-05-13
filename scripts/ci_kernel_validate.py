#!/usr/bin/env python3
"""
ci_kernel_validate.py — Headless SysML v2 kernel validator for CI/CD pipelines.

Reads sysml-project.yml at the repository root and executes the declared
layers against the SysML v2 kernel, failing on any syntax error, unresolved
name, or violated assertion.

Two layer lists are supported in sysml-project.yml:

  layers            — full list; used by --dry-run (file existence) and commit.sh.
  validation_layers — positive-test subset; used for kernel execution in CI.
                      Layers containing intentional VIOLATED assertions (negative
                      tests — e.g. FMEA.sysml, UQ.sysml) must be excluded here
                      and validated separately via Safety.ipynb.

Usage:
    python scripts/ci_kernel_validate.py           # kernel run (validation_layers)
    python scripts/ci_kernel_validate.py --dry-run  # file existence check (layers)
    python scripts/ci_kernel_validate.py --all-layers  # kernel run on ALL layers
                                                        # (may produce expected failures
                                                        #  from FMEA/UQ negative tests)

Requirements (CI):
    conda install -c conda-forge jupyter-sysml-kernel=0.58.0 nbclient nbformat
    OR:
    pip install nbclient nbformat  (kernel must already be registered separately)

Known limitations:
  - RAAML 'metadata def' syntax requires SysML v2 Pilot JAR >= 2022-06.
    If the kernel rejects RAAML.sysml, replace 'metadata def' with 'attribute def'
    (see fallback mode documented in bilgepump/RAAML.sysml).
  - The kernel validates syntax and positive-test assertions only.  Constraint
    expressions in verify.sh and Safety.ipynb are evaluated in Python, not by
    the kernel — they use regex + eval and do not have full SysML type semantics.

Adapting for a new project:
    Edit sysml-project.yml — change 'name', 'layers', and 'validation_layers'.
    This script is generic and requires no modification.
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST  = os.path.join(REPO_ROOT, "sysml-project.yml")


# ---------------------------------------------------------------------------
# sysml-project.yml reader — no pyyaml dependency
#
# Only parses the fields used by this script: 'name' and 'layers'.
# The YAML subset used in the manifest is intentionally simple (no anchors,
# no multi-line strings, no nested dicts under layers) so a line-by-line
# parser is entirely sufficient and avoids an extra dependency.
# ---------------------------------------------------------------------------

def read_manifest(path: str) -> tuple:
    """Return (name, layers, validation_layers) from sysml-project.yml.

    validation_layers is None when the key is absent from the manifest.
    In that case callers should fall back to layers.
    """
    name = "SysMLProject"
    layers: list = []
    validation_layers: list | None = None
    current_list: list | None = None  # which list we are currently appending to
    with open(path) as fh:
        for raw_line in fh:
            s = raw_line.strip()
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
            elif current_list is not None and not s.startswith("- "):
                # Any non-list line ends the active list block
                current_list = None
    return name, layers, validation_layers


# ---------------------------------------------------------------------------
# Dry-run: verify all layer files exist and print the execution order
# ---------------------------------------------------------------------------

def dry_run(name: str, layers: list, validation_layers: list | None = None) -> None:
    print(f"DRY RUN  —  project: {name}")
    vl_set = set(validation_layers) if validation_layers else set(layers)
    print(f"  {len(layers)} layer(s) in manifest order")
    if validation_layers is not None:
        excluded = [l for l in layers if l not in vl_set]
        if excluded:
            print(f"  {len(excluded)} layer(s) excluded from kernel CI (negative tests — validated by Safety.ipynb):")
            for e in excluded:
                print(f"    - {e}")
    print()
    missing = []
    for i, fname in enumerate(layers, 1):
        path = os.path.join(REPO_ROOT, fname)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  [{i}] {fname:<40} {size:>7} bytes  OK")
        else:
            print(f"  [{i}] {fname:<40}           MISSING")
            missing.append(fname)
    if missing:
        print(f"\nERROR: {len(missing)} layer file(s) not found in repository root.",
              file=sys.stderr)
        sys.exit(1)
    print("\nDry run passed — all layer files present.")


# ---------------------------------------------------------------------------
# Full validation via nbclient
# ---------------------------------------------------------------------------

def validate(name: str, layers: list) -> None:
    # Import here so --dry-run works even without nbformat/nbclient installed.
    try:
        import nbformat  # noqa: PLC0415
        from nbclient import NotebookClient  # noqa: PLC0415
        from nbclient.exceptions import CellExecutionError  # noqa: PLC0415
    except ImportError as exc:
        print(
            f"ERROR: {exc}\n\n"
            "Install CI dependencies and re-run:\n"
            "  conda install -c conda-forge nbclient nbformat\n"
            "  or:  pip install nbclient nbformat\n\n"
            "To skip kernel execution use:  --dry-run",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate all layer files exist before starting the kernel
    missing = [f for f in layers if not os.path.exists(os.path.join(REPO_ROOT, f))]
    if missing:
        print(f"ERROR: layer file(s) not found: {missing}", file=sys.stderr)
        sys.exit(1)

    print(f"=== SysML v2 Model Validation: {name} ===")
    print(f"Layers ({len(layers)}): {', '.join(layers)}\n")

    # ------------------------------------------------------------------
    # Discover the SysML v2 kernel name.
    #
    # The jupyter-sysml-kernel package registers itself under a name that
    # may vary by version: 'sysml2', 'sysml', or another variation.
    # We search all installed kernelspecs for one whose display name or
    # key contains 'sysml'. This avoids hardcoding 'sysml2' and breaking
    # when the kernel package uses a different registration name.
    # ------------------------------------------------------------------
    try:
        import jupyter_client  # noqa: PLC0415
        installed_kernels = jupyter_client.kernelspec.find_kernel_specs()
    except Exception:
        installed_kernels = {}

    kernel_name = None
    # Prefer exact matches: 'sysml2' first, then 'sysml', then any sysml* key
    for candidate in ("sysml2", "sysml"):
        if candidate in installed_kernels:
            kernel_name = candidate
            break
    if kernel_name is None:
        for k in installed_kernels:
            if "sysml" in k.lower():
                kernel_name = k
                break
    if kernel_name is None:
        print(
            f"ERROR: No SysML v2 kernel found.\n"
            f"Installed kernels: {list(installed_kernels.keys())}\n\n"
            "Install with:  conda install -c conda-forge jupyter-sysml-kernel",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Using kernel: {kernel_name}  (from {list(installed_kernels.keys())})")

    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "SysML v2",
        "language": "sysml",
        "name": kernel_name,
    }
    for layer_file in layers:
        with open(os.path.join(REPO_ROOT, layer_file)) as fh:
            source = fh.read()
        nb.cells.append(nbformat.v4.new_code_cell(source))

    # ------------------------------------------------------------------
    # Execute the notebook.
    #
    # NotebookClient.execute() is a synchronous call that:
    #   1. Starts the sysml2 kernel (Java process via jupyter-sysml-kernel)
    #   2. Sends each cell to the kernel in order
    #   3. Collects outputs back into nb.cells[i].outputs
    #   4. Raises CellExecutionError on the first cell that produces an
    #      'error' output (syntax error, unresolved name, failed assert, …)
    #   5. Shuts the kernel down cleanly on exit
    #
    # timeout=300: generous for kernel JVM startup on a cold CI runner.
    # kernel_name: auto-discovered from installed kernelspecs at runtime.
    # ------------------------------------------------------------------
    client = NotebookClient(
        nb,
        timeout=300,
        kernel_name=kernel_name,
        resources={"metadata": {"path": REPO_ROOT}},
    )

    print("Starting SysML v2 kernel...")
    try:
        client.execute()
    except CellExecutionError as exc:
        # Find which cell(s) have error outputs and print clean diagnostics
        print("\nVALIDATION FAILED\n", file=sys.stderr)
        for i, cell in enumerate(nb.cells):
            cell_errors = [
                o for o in cell.get("outputs", []) if o.get("output_type") == "error"
            ]
            if cell_errors:
                print(f"  Layer [{i + 1}/{len(layers)}]: {layers[i]}", file=sys.stderr)
                for err in cell_errors:
                    ename  = err.get("ename", "Error")
                    evalue = err.get("evalue", "")
                    print(f"  {ename}: {evalue}", file=sys.stderr)
                    for tb_line in err.get("traceback", []):
                        # Strip ANSI colour codes so CI logs are readable
                        clean = tb_line
                        try:
                            import re
                            clean = re.sub(r"\x1b\[[0-9;]*m", "", tb_line)
                        except Exception:
                            pass
                        print(f"    {clean}", file=sys.stderr)
                print(file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\nERROR: Kernel execution failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Double-check outputs even if no exception was raised (some kernels use
    # stream outputs instead of error outputs for certain failure modes).
    errors = [
        (layers[i], cell)
        for i, cell in enumerate(nb.cells)
        if any(o.get("output_type") == "error" for o in cell.get("outputs", []))
    ]
    if errors:
        print("\nVALIDATION FAILED — error output detected in cells:\n", file=sys.stderr)
        for layer_file, cell in errors:
            print(f"  {layer_file}", file=sys.stderr)
        sys.exit(1)

    # All cells passed — print per-layer summary
    print()
    for i, cell in enumerate(nb.cells):
        # Collect any non-error stream output for visibility
        stream_lines = []
        for o in cell.get("outputs", []):
            if o.get("output_type") == "stream":
                stream_lines.append(o.get("text", "").strip())
        summary = f" ({'; '.join(stream_lines)})" if stream_lines else ""
        print(f"  [{i + 1}/{len(layers)}] {layers[i]}  OK{summary}")

    print(f"\nVALIDATION PASSED — {len(layers)}/{len(layers)} layers compiled successfully.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Headless SysML v2 model validator — reads sysml-project.yml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify all layer files exist and print the execution plan; do not start the kernel",
    )
    parser.add_argument(
        "--all-layers",
        action="store_true",
        help=(
            "Run the kernel against ALL layers (ignores validation_layers). "
            "Expect failures from FMEA/UQ negative-test analysis defs."
        ),
    )
    parser.add_argument(
        "--manifest",
        default=MANIFEST,
        metavar="PATH",
        help=f"Path to sysml-project.yml (default: {MANIFEST})",
    )
    args = parser.parse_args()

    if not os.path.exists(args.manifest):
        print(f"ERROR: manifest not found: {args.manifest}\n"
              "Create sysml-project.yml at the repository root.", file=sys.stderr)
        sys.exit(1)

    name, layers, validation_layers = read_manifest(args.manifest)

    if not layers:
        print("ERROR: sysml-project.yml contains no 'layers' entries.", file=sys.stderr)
        sys.exit(1)

    # Determine which layer set to use for kernel execution.
    # --dry-run always uses the full 'layers' list (checks all files exist).
    # --all-layers overrides validation_layers (useful for local debugging).
    # Default: use validation_layers if present, else fall back to layers.
    if args.dry_run:
        dry_run(name, layers, validation_layers)
    elif args.all_layers:
        print("NOTE: --all-layers set — running kernel on ALL layers.")
        print("      FMEA/UQ negative-test violations are expected and will cause failures.\n")
        validate(name, layers)
    else:
        kernel_layers = validation_layers if validation_layers is not None else layers
        if validation_layers is not None and len(validation_layers) < len(layers):
            excluded = [l for l in layers if l not in set(validation_layers)]
            print(f"NOTE: {len(excluded)} layer(s) excluded from kernel CI "
                  f"(negative tests — see validation_layers in sysml-project.yml):")
            for e in excluded:
                print(f"      - {e}")
            print()
        validate(name, kernel_layers)


if __name__ == "__main__":
    main()
