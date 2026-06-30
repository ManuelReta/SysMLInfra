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

        for layer in self.all_layers:
            with open(self.project_dir / layer, "r") as f:
                text = f.read()

            package, req_usages, parts = parse_sysml(text)
            commands = generate_eval_commands(package, req_usages, parts)
            all_commands += commands

        print("Generated %eval commands:\n")
        for c in all_commands:
            print(c)
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
            text = result["out"][0]["data"]["text/plain"]
            match_found = bool(re.search(r"\btrue\b", text))
            logging.info(f"Requirement {requirement}: {match_found}")


if __name__ == "__main__":
    p = Pipeline(
        Path(
            "/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/SysMLInfra/tests/sys_infra/test_models/layered_simple_pump/build/LayeredTestModel_0.0.1"
        )
    )
    p()
