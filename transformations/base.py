from typing import Any, Sequence, TypedDict
from z3 import Int, Solver
import numpy as np
from features.base import MAX_FEATURES

MAX_SIZE = 32
MAX_COLOR = 9

class MinMax(TypedDict):
    min: int
    max: int

class FeatureConfig(MinMax):
    in_slots: dict[int, MinMax]
    out_slots: dict[int, MinMax]

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
    config: dict[str, FeatureConfig] = {}
    REGISTRY: dict[str, type[ARCTransformation]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.REGISTRY[cls.__name__] = cls

        merged_config = {}
        for base in reversed(cls.__mro__):
            if hasattr(base, 'config'):
                for key, config in base.config.items():
                    merged_config[key] = config
        cls.config = merged_config

    @classmethod
    def register_features(cls, features: set[str]):
        features |= cls.config.keys()

    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str, pre_phase: bool, feature_types: set[str], feature_slots: list[tuple[int, int, int]]):
        # 1. Base geometric constraints
        for prop in ["width", "height"]:
            for i in range(cls.in_count):
                var = Int(f"{id}_in_{i}_{prop}")
                solver.add(var >= 1, var <= MAX_SIZE)
            for i in range(cls.out_count):
                var = Int(f"{id}_out_{i}_{prop}")
                solver.add(var >= 1, var <= MAX_SIZE)
        
        # 2. Feature state constraints
        for key in feature_types:
            config = cls.config.get(key, {})
            
            # --- INPUT SLOTS ---
            sum_in = 0
            for i in range(cls.in_count):
                var = Int(f"{id}_{key}_in_{i}_count")
                sum_in += var
                
                in_slot_config: MinMax = config.get("in_slots", {}).get(i)
                solver.add(var >= in_slot_config.get("min", 0), var <= in_slot_config.get("max", MAX_FEATURES))
            
            # --- OUTPUT SLOTS ---
            sum_out = 0
            for i in range(cls.out_count):
                var = Int(f"{id}_{key}_out_{i}_count")
                sum_out += var
                
                out_slot_config: MinMax = config.get("out_slots", {}).get(i)
                solver.add(var >= out_slot_config.get("min", 0), var <= out_slot_config.get("max", MAX_FEATURES))
            
            # --- DELTA (NET CHANGE) LOGIC ---
            count = Int(f"{id}_{key}_count")
            solver.add(count >= config.get("min", 0))
            solver.add(count <= config.get("max", 0))
            solver.add(sum_out == sum_in + count)

    def __init__(self, parameters: dict[str, Any]):
        self.parameters = parameters

    def execute(self, inputs: Sequence[np.ndarray]) -> tuple[np.ndarray]:
        """
        Pure, deterministic matrix execution.
        Takes a tuple of required input arrays and computes output arrays.
        """
        raise NotImplementedError

    def describe(self, inputs: Sequence[np.ndarray]) -> str:
        """
        Synthesizes an exact, unambiguous text explanation of the logic step
        using the concrete runtime values and parameters.
        """
        raise NotImplementedError

class CreateCanvas(ARCTransformation):
    """
    First transformation of every puzzle. Accepts 0 inputs.
    Generates list of empty training inputs and list of empty test inputs
    """
    in_count = 0

    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str, pre_phase: bool, feature_types: set[str], feature_slots: list[tuple[int, int, int]]):
        super().register_variables_and_constraints(solver, id, pre_phase, feature_types, feature_slots)

        background = Int(f"background")
        
        solver.add(background >= 0, background <= MAX_COLOR)

class Dummy(ARCTransformation):
    """
    Transformation that does nothing
    """
    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str, pre_phase: bool, feature_types: set[str], feature_slots: list[tuple[int, int, int]]):
        super().register_variables_and_constraints(solver, id, pre_phase, feature_types, feature_slots)

        in_w, out_w = Int(f"{id}_in_0_width"), Int(f"{id}_out_0_width")
        in_h, out_h = Int(f"{id}_in_0_height"), Int(f"{id}_out_0_height")
        
        solver.add(in_w == out_w)
        solver.add(in_h == out_h)

        out_indices: dict[int, int] = {}
        for in_wire, index, out_wire in feature_slots:
            out_index = out_indices.get(out_wire, -1) + 1
            out_indices[out_wire] = out_index
            for prop in ["type", "x", "y", "width", "height", "color", "mask"]:
                in_var = Int(f"{id}_in_{in_wire}_{index}_{prop}")
                out_var = Int(f"{id}_out_{out_wire}_{out_index}_{prop}")
                solver.add(in_var == out_var)
