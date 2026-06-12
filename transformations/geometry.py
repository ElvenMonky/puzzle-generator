from z3 import And, If, Int, Solver
from transformations.base import ARCTransformation, MAX_SIZE

class BaseUpscale(ARCTransformation):
    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str):
        super().register_variables_and_constraints(solver, id)

        in_w, out_w, scale_w = Int(f"{id}_in_0_width"), Int(f"{id}_out_0_width"), Int(f"{id}_param_w_scale")
        in_h, out_h, scale_h = Int(f"{id}_in_0_height"), Int(f"{id}_out_0_height"), Int(f"{id}_param_h_scale")
        
        solver.add(scale_w >= 1, scale_w <= MAX_SIZE)
        solver.add(scale_h >= 1, scale_h <= MAX_SIZE)
        solver.add(scale_w + scale_h >= 3)
        solver.add(in_w * scale_w == out_w, in_h * scale_h == out_h)

class Tile(BaseUpscale):
    pass

class Upscale(BaseUpscale):
    pass

class Merge(ARCTransformation):
    in_count = 2
    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str):
        super().register_variables_and_constraints(solver, id)
        
        in_w0, in_w1, out_w = Int(f"{id}_in_0_width"), Int(f"{id}_in_1_width"), Int(f"{id}_out_0_width")
        in_h0, in_h1, out_h = Int(f"{id}_in_0_height"), Int(f"{id}_in_1_height"), Int(f"{id}_out_0_height")
        
        solver.add(in_w0 == in_w1, in_w1 == out_w)
        solver.add(in_h0 == in_h1, in_h1 == out_h)

class Split(ARCTransformation):
    out_count = 2
    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str):
        super().register_variables_and_constraints(solver, id)
        
        # Define internal parameters
        direction = Int(f"{id}_param_direction")
        start = Int(f"{id}_param_start")
        width = Int(f"{id}_param_width")
        
        # Bound the parameters
        solver.add(direction >= 0, direction <= 1)
        solver.add(start >= 1, start < MAX_SIZE)
        solver.add(width >= 1, width < MAX_SIZE)

        in_w, out_w0, out_w1 = Int(f"{id}_in_0_width"), Int(f"{id}_out_0_width"), Int(f"{id}_out_1_width")
        in_h, out_h0, out_h1 = Int(f"{id}_in_0_height"), Int(f"{id}_out_0_height"), Int(f"{id}_out_1_height")

        solver.add(If(direction == 1, And(
            in_w == out_w1, out_w0 == out_w1,
            out_h0 == start,
            in_h == out_h0 + width + out_h1
        ), And(
            in_h == out_h0, out_h0 == out_h1,
            out_w0 == start,
            in_w == out_w0 + width + out_w1
        )))
