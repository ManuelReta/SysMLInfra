import os
import sys
from pathlib import Path
# ---------------------------------------------------------------------------
# Dry-run: verify all layer files exist and print the execution order
# ---------------------------------------------------------------------------


def dry_runner(
    name: str, layers: list, project_dir: Path, validation_layers: list | None = None
) -> None:
    print(f"DRY RUN  —  project: {name}")
    vl_set = set(validation_layers) if validation_layers else set(layers)
    print(f"  {len(layers)} layer(s) in manifest order")
    if validation_layers is not None:
        excluded = [layer for layer in layers if layer not in vl_set]
        if excluded:
            print(
                f"  {len(excluded)} layer(s) excluded from kernel CI (negative tests — validated by Safety.ipynb):"
            )
            for e in excluded:
                print(f"    - {e}")
    print()
    missing = []
    for i, fname in enumerate(layers, 1):
        path = os.path.join(project_dir, fname)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  [{i}] {fname:<40} {size:>7} bytes  OK")
        else:
            print(f"  [{i}] {fname:<40}           MISSING")
            missing.append(fname)
    if missing:
        print(
            f"\nERROR: {len(missing)} layer file(s) not found in repository root.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("\nDry run passed — all layer files present.")
