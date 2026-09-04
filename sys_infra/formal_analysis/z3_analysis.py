import logging
from z3 import Real, Solver


class Z3SolverParser:
    def __init__(self):
        self.solver = Solver()
        self.symbols = {}

    def add_constraint(self, constraint_def):
        for name in constraint_def["inputs"]:
            self.symbols[name] = Real(name)

        self.symbols[constraint_def["result"]] = Real(constraint_def["result"])

        # Parse expression into Z3 expression
        rhs = eval(constraint_def["expression"], {}, self.symbols)

        self.solver.add(self.symbols[constraint_def["result"]] == rhs)
        check = self.solver.check()
        m = self.solver.model()

        logging.info(
            f"Model: {constraint_def['result']} = {m[self.symbols[constraint_def['result']]]} (check: {check})"
        )

    def add_values(self, values: dict[str, float]):
        # Add known values
        for name, value in values.items():
            if name in self.symbols:
                self.solver.add(self.symbols[name] == value)

    def check_constraints(self):
        check = self.solver.check()
        logging.info(f"Z3 check result: {check}")
