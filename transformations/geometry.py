from z3 import And, If, Int, Solver
from transformations.base import ARCTransformation, MAX_SIZE

class BaseUpscale(ARCTransformation):
    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str, pre_phase: bool, features: set[str], feature_ids: list[str]):
        super().register_variables_and_constraints(solver, id, pre_phase, features, feature_ids)

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
    def register_variables_and_constraints(cls, solver: Solver, id: str, pre_phase: bool, features: set[str], feature_ids: list[str]):
        super().register_variables_and_constraints(solver, id, pre_phase, features, feature_ids)
        
        in_w0, in_w1, out_w = Int(f"{id}_in_0_width"), Int(f"{id}_in_1_width"), Int(f"{id}_out_0_width")
        in_h0, in_h1, out_h = Int(f"{id}_in_0_height"), Int(f"{id}_in_1_height"), Int(f"{id}_out_0_height")
        
        solver.add(in_w0 == in_w1, in_w1 == out_w)
        solver.add(in_h0 == in_h1, in_h1 == out_h)

class Split(ARCTransformation):
    out_count = 2
    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str, pre_phase: bool, features: set[str], feature_ids: list[str]):
        super().register_variables_and_constraints(solver, id, pre_phase, features, feature_ids)
        
        direction = Int(f"{id}_param_direction")
        start = Int(f"{id}_param_start")
        width = Int(f"{id}_param_width")
        
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

class Rotate90(ARCTransformation):
    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str, pre_phase: bool, features: set[str], feature_ids: list[str]):
        super().register_variables_and_constraints(solver, id, pre_phase, features, feature_ids)
        
        in_w, out_w = Int(f"{id}_in_0_width"), Int(f"{id}_out_0_width")
        in_h, out_h = Int(f"{id}_in_0_height"), Int(f"{id}_out_0_height")

        times = Int(f"{id}_param_times")
        solver.add(times > 0, times < 8) # 4-7 flip before rotate
        
        solver.add(If(times % 2 == 1, And(
            in_w == out_h, in_h == out_w
        ), And(
            in_w == out_w, in_h == out_h
        )))

        for f_id in feature_ids:
            in_dir = Int(f"{id}_in_0_{f_id}_direction")
            out_dir = Int(f"{id}_out_0_{f_id}_direction")
            in_start = Int(f"{id}_in_0_{f_id}_start")
            out_start = Int(f"{id}_out_0_{f_id}_start")
            in_width = Int(f"{id}_in_0_{f_id}_width")
            out_width = Int(f"{id}_out_0_{f_id}_width")

            solver.add(out_start == in_start)
            solver.add(out_width == in_width)
            solver.add(If(times % 2 == 1, 
                out_dir == 1 - in_dir,
                out_dir == in_dir
            ))
