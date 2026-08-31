import logging
import re
from dataclasses import dataclass, field


@dataclass
class SysMLConstraint:
    name: str
    inputs: dict[str, str]
    output: str
    expression: str


@dataclass
class SysMLModel:
    package: str
    req_defs: dict[str, str]
    req_usages: list[tuple[str, str]]
    parts: dict[str, list[str]]

    attributes: dict[str, str] = field(default_factory=dict)
    constraints: list[SysMLConstraint] = field(default_factory=list)
    constraint_defs: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class ConstraintDef:
    name: str
    inputs: dict[str, str]
    output: str
    expression: str


class ParseSysml:
    def parse_requirement_defs(
        self, text: str, req_defs: dict[str, str]
    ) -> dict[str, str]:
        # -------------------------------------------------------
        # Requirement definitions
        # -------------------------------------------------------
        for match in re.finditer(
            r"requirement\s+def\s+(\w+)\s*{([^}]*)}",
            text,
            re.DOTALL,
        ):
            name = match.group(1)
            body = match.group(2)

            if re.search(r"require\s+constraint\s*{", body):
                logging.error(
                    f"Requirement '{name}' contains unsupported "
                    f"'require constraint' block."
                )
                continue

            attr_match = re.search(r"attribute\s+(\w+)\s*:", body)

            if attr_match:
                req_defs[name] = attr_match.group(1)
        return req_defs

    def parse_requirements(
        self, text: str, req_defs, req_usages: list[tuple[str, str]] = []
    ) -> list[tuple[str, str]]:
        # -------------------------------------------------------
        # Requirement usages
        # -------------------------------------------------------
        for match in re.finditer(
            r"requirement\s+(?:<([^>]+)>\s+)?(\w+)\s*:\s*(\w+)",
            text,
        ):
            tag = match.group(1)
            name = match.group(2)
            typename = match.group(3)

            attr = req_defs.get(typename)

            if attr:
                req_usages.append((tag if tag else name, attr))
        return req_usages

    @staticmethod
    def parse_constraint_defs(text: str):
        constraints = {}

        pattern = re.compile(
            r"constraint\s+def\s+(\w+)\s*{([^}]*)}",
            re.DOTALL,
        )

        for match in pattern.finditer(text):
            name = match.group(1)
            body = match.group(2)

            inputs = {}

            for inp in re.finditer(r"in\s+(\w+)\s*:\s*(\w+)\s*;", body):
                inputs[inp.group(1)] = inp.group(2)

            expr_match = re.search(
                r"attribute\s+(\w+)\s*=\s*(.*?);",
                body,
                re.DOTALL,
            )

            result_name = None
            expression = None

            if expr_match:
                result_name = expr_match.group(1)
                expression = expr_match.group(2).strip()

            constraints[name] = {
                "inputs": inputs,
                "result": result_name,
                "expression": expression,
            }

        return constraints

    def parse_parts(self, text: str, parts={}) -> dict[str, list[str]]:
        # -------------------------------------------------------
        # Parts
        # -------------------------------------------------------
        for match in re.finditer(
            r"part\s+(\w+)\s*:\s*(\w+)\s*{([^}]*)}",
            text,
            re.DOTALL,
        ):
            part_name = match.group(1)
            body = match.group(3)

            attributes = re.findall(
                r":>>\s*(\w+)",
                body,
            )

            parts[part_name] = attributes
        return parts

    def parse_attributes(self, text: str, attributes={}) -> dict[str, str]:
        # -------------------------------------------------------
        # Attribute definitions
        # -------------------------------------------------------
        for match in re.finditer(
            r"attribute\s+def\s+(\w+)(?:\s*:\>\s*([\w:]+))?",
            text,
        ):
            attributes[match.group(1)] = match.group(2) or "Real"
        return attributes

    def parse_constraints(self, text: str, constraints=[]) -> list[SysMLConstraint]:
        # -------------------------------------------------------
        # Constraints
        # -------------------------------------------------------
        for match in re.finditer(
            r"constraint\s+def\s+(\w+)\s*{(.*?)}",
            text,
            re.DOTALL,
        ):
            c_name = match.group(1)
            body = match.group(2)

            inputs = {}

            for inp in re.finditer(
                r"in\s+(\w+)\s*:\s*(\w+)",
                body,
            ):
                alias = inp.group(1)
                typename = inp.group(2)

                inputs[alias] = typename

            eq = re.search(
                r"attribute\s+(\w+)\s*=\s*(.*?);",
                body,
                re.DOTALL,
            )

            if not eq:
                continue

            constraints.append(
                SysMLConstraint(
                    name=c_name,
                    inputs=inputs,
                    output=eq.group(1),
                    expression=eq.group(2).strip(),
                )
            )
        return constraints

    def __call__(self, text, existing_req_defs):
        package_match = re.search(r"package\s+(\w+)", text)
        package = package_match.group(1) if package_match else "Unknown"

        logging.info(f"Parsing SysML text for package: {package}")

        req_defs = self.parse_requirement_defs(text=text, req_defs=existing_req_defs)
        req_usages = self.parse_requirements(
            text=text, req_defs=req_defs, req_usages=[]
        )
        parts = self.parse_parts(text=text)
        attributes = self.parse_attributes(text=text)
        constraints = self.parse_constraints(text=text)

        constraint_defs = self.parse_constraint_defs(text=text)

        return SysMLModel(
            package=package,
            req_defs=req_defs,
            req_usages=req_usages,
            parts=parts,
            attributes=attributes,
            constraints=constraints,
            constraint_defs=constraint_defs,
        )
