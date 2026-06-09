import argparse
import os
import sys
from dotenv import load_dotenv
from scripts.bootstrap_traceability import run_trace
from scripts.ci_kernel_validate import run_validate
from scripts.debug_kernel_eval import run_eval
from scripts.sensor_adapter import run_sensor
from scripts.sysml_check import run_check
from sys_infra.verify import run_verify
from pathlib import Path

load_dotenv()
default_project_dir = (
    Path(os.getenv("REPO_ROOT", ".")) / "examples" / "bilgepump"
)  # default to current directory if not set


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sysml",
        description="SysML toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # -------------------------
    # GLOBAL (shared)
    # -------------------------
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # =========================================================
    # CHECK - sysml_check.py
    # =========================================================
    check = subparsers.add_parser("check", help="Check SysML files")

    check.add_argument(
        "--project-dir",
        default=default_project_dir,
        help="Project directory",
    )
    check.add_argument(
        "targets",
        nargs="+",
        metavar="FILE.sysml",
    )
    check.add_argument("--fallback", action="store_true")
    check.add_argument("--expect-violations", action="store_true")

    # =========================================================
    # VERIFY
    # =========================================================
    verify = subparsers.add_parser("verify", help="Run verification")

    verify.add_argument(
        "--project-dir", default=default_project_dir, help="Project directory"
    )
    verify.add_argument("--dry-run", action="store_true")
    verify.add_argument("--negative", action="store_true")
    verify.add_argument("--all", action="store_true")
    verify.add_argument("--fallback", action="store_true")
    verify.add_argument("--require-kernel", action="store_true")
    verify.add_argument("--visual", action="store_true")
    verify.add_argument("--publish", action="store_true")
    verify.add_argument("--z3", action="store_true")
    verify.add_argument("--live", metavar="CONFIG")

    # =========================================================
    # SENSOR
    # =========================================================
    sensor = subparsers.add_parser("sensor", help="Sensor adapter")

    sensor.add_argument("--config", metavar="FILE")
    sensor.add_argument("--demo", action="store_true")
    sensor.add_argument("--once", action="store_true")
    sensor.add_argument("--interval", type=float, default=5.0)
    sensor.add_argument(
        "--output",
        choices=["json", "pretty"],
        default="pretty",
    )

    # =========================================================
    # VALIDATE (manifest validator)
    # =========================================================
    validate = subparsers.add_parser("validate", help="Validate project")

    validate.add_argument("--dry-run", action="store_true")
    validate.add_argument("--all-layers", action="store_true")
    validate.add_argument(
        "--manifest", default=default_project_dir / "sysml-project.yml"
    )

    # =========================================================
    # TRACEABILITY
    # =========================================================
    trace = subparsers.add_parser("trace", help="Bootstrap traceability")

    trace.add_argument("--dry-run", action="store_true")
    trace.add_argument("--verbose", action="store_true")

    # =========================================================
    # EVAL (your simple script)
    # =========================================================
    eval_cmd = subparsers.add_parser("eval", help="Eval/test mode")

    eval_cmd.add_argument("--negative", action="store_true")
    eval_cmd.add_argument("--raw", action="store_true")

    return parser


def main() -> None:
    args = create_parser().parse_args()
    if args.command == "check":
        run_check(args)

    elif args.command == "verify":
        run_verify(args)

    elif args.command == "sensor":
        run_sensor(args)

    elif args.command == "validate":
        run_validate(args)

    elif args.command == "trace":
        run_trace(args)

    elif args.command == "eval":
        run_eval(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
