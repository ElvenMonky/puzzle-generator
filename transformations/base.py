from typing import Any, Sequence
from z3 import Int, Solver
import numpy as np

MAX_SIZE = 32

class ARCTransformation:
    """
    The formal contract for an ARC Transformation.
    Transformations are building blocks of ARC puzzles.
    Every puzzle is a sequence of individual transformations
    where next transformation can use zero, one
    or multiple outputs from previous transformations
    """
    in_count = 1
    out_count = 1
    REGISTRY = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.REGISTRY[cls.__name__] = cls

    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str):
        for prop in ["width", "height"]:
            for i in range(cls.in_count):
                var = Int(f"{id}_in_{i}_{prop}")
                solver.add(var >= 1, var <= MAX_SIZE)
            for i in range(cls.out_count):
                var = Int(f"{id}_out_{i}_{prop}")
                solver.add(var >= 1, var <= MAX_SIZE)

    def __init__(self, parameters: dict[str, Any]):
        self.parameters = parameters

    def execute(self, inputs: Sequence[np.ndarray]) -> tuple[np.ndarray]:
        """
        PASS 2 (Forward): Pure, deterministic matrix execution.
        Takes a tuple of required input arrays and computes output arrays.
        """
        raise NotImplementedError

    def describe(self, inputs: Sequence[np.ndarray]) -> str:
        """
        PASS 2 (Forward): Synthesizes an exact, unambiguous text explanation 
        of the logic step using the concrete runtime values and parameters.
        """
        raise NotImplementedError

class Canvas(ARCTransformation):
    """
    First transformation of every puzzle. Accepts 0 inputs.
    Generates list of empty training inputs and list of empty test inputs
    """
    in_count = 0

class Dummy(ARCTransformation):
    """
    Transformation that does nothing
    """
    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str):
        super().register_variables_and_constraints(solver, id)

        in_w, out_w = Int(f"{id}_in_0_width"), Int(f"{id}_out_0_width")
        in_h, out_h = Int(f"{id}_in_0_height"), Int(f"{id}_out_0_height")
        
        solver.add(in_w == out_w)
        solver.add(in_h == out_h)
