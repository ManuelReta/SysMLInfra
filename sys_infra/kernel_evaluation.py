import re
from pathlib import Path
from typing import Any
import logging
from sys_infra.formal_analysis.z3_analysis import Z3SolverParser
from sys_infra.parsing.sysml_v2_parser import ParseSysml

from sys_infra.utils import (
    SysMLProjectReader,
    generate_eval_commands,
    run_kernel_publish,
    kernel_evaluate,
    append_kernel_layers,
    _discover_sysml_kernel,
)
import nbformat

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def read_sysml_file(file_path: Path) -> str:
    with open(file_path, "r") as f:
        return f.read()


class Pipeline:
    def __init__(
        self, project_dir: Path, reader: type[SysMLProjectReader] = SysMLProjectReader
    ) -> None:
        self.project_dir = project_dir
        read_layers = reader(self.project_dir)

        self.project_name = read_layers.get_name()
        self.all_layers = read_layers.get_layers()
        self.validation_layers = read_layers.get_validation_layers()

        self.kernel_name = _discover_sysml_kernel()
        if self.kernel_name is None:
            raise ValueError("Kernel not found")

    def __call__(self, publish: bool = False) -> list[dict[Any, Any]]:
        expressions, constraint_defs = self._construct_evaluateble_expressions(
            all_layers=self.all_layers, project_dir=self.project_dir
        )
        self.nb = self._get_kernel()
        self.nb = append_kernel_layers(
            layer_paths=[self.project_dir / layer for layer in self.all_layers],
            nb=self.nb,
        )
        results = self._evaluate_expressions(expressions=expressions, nb=self.nb)

        self._run_z3_analysis(constraint_defs)

        if publish:
            self._publish_to_api()
        self._store_results(results=results)
        return results

    def _get_kernel(self):
        nb = nbformat.v4.new_notebook()
        nb.metadata["kernelspec"] = {
            "display_name": "SysML v2",
            "language": "sysml",
            "name": self.kernel_name,
        }
        return nb

    @staticmethod
    def _construct_evaluateble_expressions(
        all_layers, project_dir
    ) -> tuple[list[str], dict[str, Any]]:
        all_commands: list[str] = []
        req_defs: dict[str, str] = {}
        constraint_defs: dict[str, Any] = {}

        for layer in all_layers:
            text = read_sysml_file(project_dir / layer)

            model = ParseSysml()(text, req_defs)

            commands = generate_eval_commands(
                model.package,
                model.req_usages,
                model.parts,
            )

            all_commands.extend(commands)
            req_defs.update(model.req_defs)
            constraint_defs.update(model.constraint_defs)

        logging.info("Generated %%eval commands:")
        for cmd in all_commands:
            logging.info(f"     {cmd}")

        return all_commands, constraint_defs

    @staticmethod
    def _run_z3_analysis(constraint_defs: dict[str, Any]) -> None:
        solver = Z3SolverParser()

        for name, constraint_def in constraint_defs.items():
            logging.info(f"Adding constraint {name}")
            solver.add_constraint(constraint_def)

        solver.add_values({})
        solver.check_constraints()

    def _evaluate_expressions(self, expressions, nb) -> list[dict[Any, Any]]:
        if self.kernel_name is None:
            raise ValueError("Kernel not found")
        results = kernel_evaluate(
            expressions=expressions,
            kernel_name=self.kernel_name,
            project_dir=self.project_dir,
            nb=nb,
        )
        return results

    def _publish_to_api(self):
        run_kernel_publish(
            self.all_layers, self.kernel_name, self.project_dir, self.project_name
        )

    def _store_results(self, results):
        logging.info("Evaluation Results:")
        for result in results:
            requirement = result["in"]

            if "%eval" not in requirement:
                continue

            if len(result["out"]) == 0:
                logging.warning(f"No output for {requirement}")
                continue

            text = result["out"][-1]["data"]["text/plain"]

            match_found = bool(re.search(r"\btrue\b", text, re.IGNORECASE))

            logging.info(
                f"      Requirement: {requirement} | "
                f"      Output: {text.strip()} | "
                f"      Passed: {match_found}"
            )


if __name__ == "__main__":
    # "/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/SysMLInfra/tests/sys_infra/test_models/layered_simple_pump"

    p = Pipeline(Path("/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/ship_coefficients"))
    p(publish=False)
