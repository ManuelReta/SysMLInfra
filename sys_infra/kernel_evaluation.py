import re

from pathlib import Path
from typing import Any
import logging
from sys_infra.utils import (
    SysMLProjectReader,
    generate_eval_commands,
    parse_sysml,
    run_kernel_publish,
    kernel_evaluate,
    append_kernel_layers,
    _discover_sysml_kernel,
)
import nbformat

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


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
        expressions = self._construct_evaluateble_expressions()
        self.nb = self._get_kernel()
        self.nb = append_kernel_layers(
            layer_paths=[self.project_dir / layer for layer in self.all_layers],
            nb=self.nb,
        )
        results = self._evaluate_expressions(expressions=expressions, nb=self.nb)
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

    def _construct_evaluateble_expressions(self) -> list[str]:
        all_commands: list[str] = []
        req_defs: dict[str, str] = {}
        for layer in self.all_layers:
            with open(self.project_dir / layer, "r") as f:
                text = f.read()

            package, req_usages, parts, new_req_defs = parse_sysml(text, req_defs)
            commands = generate_eval_commands(package, req_usages, parts)
            all_commands += commands
            req_defs.update(new_req_defs)

        logging.info("Generated %eval commands:\n")
        for c in all_commands:
            logging.info(f" {c}")
        return all_commands

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
                f"Requirement: {requirement} | "
                f"Output: {text.strip()} | "
                f"Passed: {match_found}"
            )


if __name__ == "__main__":
    # "/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/SysMLInfra/tests/sys_infra/test_models/layered_simple_pump"

    p = Pipeline(Path("/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/ship_coefficients"))
    p(publish=False)
