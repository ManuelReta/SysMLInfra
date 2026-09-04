import re
from pathlib import Path
from typing import Any
import logging

from sys_infra.formal_analysis.z3_analysis import Z3SolverParser
from sys_infra.parsing.sysml_v2_parser import ParseSysMLAst, ParseSysml
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
        self.values = self._parse_evaluated_expressions(results=results)
        return results

    def _parse_evaluated_expressions(self, results: list[dict[Any, Any]]) -> dict[str, bool]:
        values = {}

        for cell in results:
            inp = cell.get("in", "")

            if not inp.startswith("%eval "):
                continue

            expr = inp.replace("%eval ", "").strip()

            for output in cell.get("out", []):
                text = output.get("data", {}).get("text/plain", "")

                m = re.search(
                    r"Literal(Integer|Real|Boolean|Rational)\s+([^\s]+)",
                    text
                )

                if m:
                    value_type = m.group(1)
                    value = m.group(2)

                    if value_type == "Integer":
                        value = int(value)
                    elif value_type == "Real":
                        value = float(value)
                    elif value_type == "Boolean":
                        value = value.lower() == "true"
                    elif value_type == "Rational":
                        value = float(value)

                    values[expr] = value

        return values

    def _get_kernel(self):
        nb = nbformat.v4.new_notebook()
        nb.metadata["kernelspec"] = {
            "display_name": "SysML v2",
            "language": "sysml",
            "name": self.kernel_name,
        }
        return nb


    def _construct_evaluateble_expressions(self,
        all_layers, project_dir
    ) -> tuple[list[str], dict[str, Any]]:
        all_commands: list[str] = []
        req_defs: dict[str, str] = {}
        constraint_defs: dict[str, Any] = {}
        self.nb = self._get_kernel()
        self.nb = append_kernel_layers(
            layer_paths=[self.project_dir / layer for layer in self.all_layers],
            nb=self.nb,
        )
        show_expressions = []
        for layer in all_layers:
            logging.info(f"Processing layer: {layer}")
            if str(layer) == "/home/sinkaa/code/mons_wp1/ship_model/Architecture.sysml":
                logging.info(f"Skipping layer: {layer}")
            text = read_sysml_file(project_dir / layer)

            # model = parser.parse(text)
            model = ParseSysml()(text, req_defs)
            show_expressions.append(f"%show {model.package}")

        results = kernel_evaluate(
            expressions=show_expressions,
            kernel_name=self.kernel_name,
            project_dir=self.project_dir,
            nb=self.nb,
        )

        package_asts = {}
        for result in results:
            if not result["in"].startswith("%show"):
                continue
            if not result["out"]:
                continue
            output = result["out"][0]
            ast_text = output["data"]["text/plain"]
            model = ParseSysMLAst().parse(ast_text)
            package_asts[model.package] = model

        eval_params = []

        for model in package_asts.values():
            for param in model.catalog:
                eval_params.append(f"%eval {param}")

        logging.info("Generated %%eval commands:")
        for cmd in eval_params:
            logging.info(f"     {cmd}")

        return eval_params, constraint_defs

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
    # p = Pipeline(Path("/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/ship_coefficients"))

    p = Pipeline(Path("/home/sinkaa/code/mons_wp1/ship_model"))
    p(publish=False)
