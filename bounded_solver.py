import random
from dataclasses import dataclass, field
from typing import Optional
from z3 import Int, Solver, sat, ModelRef

@dataclass
class BoundedSolver:
    solver: Optional[Solver] = field(default=None, init=False, repr=False, compare=False)
    bw: Optional[Int] = field(default=None, init=False, repr=False, compare=False)
    bh: Optional[Int] = field(default=None, init=False, repr=False, compare=False)
    result: Optional[dict] = field(default=None, init=False, repr=False, compare=False)

    def get_prefix(self) -> str:
        return id(self)

    def add_constraints(self) -> Optional[dict]:
        pass

    def init_solver(self) -> Solver:
        if self.solver is not None:
            return self.solver
        self.bw = Int(f"{self.get_prefix()}.w")
        self.bh = Int(f"{self.get_prefix()}.h")
        self.solver = Solver()
        self.result = self.add_constraints()
        return self.solver

    def generate_model(self, width: int, height: int, rng: Optional[random.Random] = None) -> ModelRef:
        solver = self.init_solver()
        solver.set("random_seed", (rng or random).randint(0, 2**31 - 1))
        solver.push()
        solver.add(self.bw == width, self.bh == height)
        try:
            if solver.check() != sat:
                raise ValueError(f"{self.get_prefix()}: unsat for {width}x{height}")
            return solver.model()
        finally:
            solver.pop()
