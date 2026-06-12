from z3 import And, If, Int, Solver
from transformations.base import ARCTransformation, MAX_SIZE

class AddGridLines(ARCTransformation):
    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str):
        super().register_variables_and_constraints(solver, id)

        h_count = Int(f"{id}_param_h_count")
        h_start = Int(f"{id}_param_h_start")
        h_width = Int(f"{id}_param_h_width")
        h_gap   = Int(f"{id}_param_h_gap")

        v_count = Int(f"{id}_param_v_count")
        v_start = Int(f"{id}_param_v_start")
        v_width = Int(f"{id}_param_v_width")
        v_gap   = Int(f"{id}_param_v_gap")

        solver.add(h_count >= 0, h_count <= MAX_SIZE // 2 + 1)
        solver.add(v_count >= 0, v_count <= MAX_SIZE // 2 + 1)
        solver.add(h_width >= 1, h_width < MAX_SIZE)
        solver.add(v_width >= 1, v_width < MAX_SIZE)
        solver.add(h_gap >= 1, h_gap < MAX_SIZE)
        solver.add(v_gap >= 1, v_gap < MAX_SIZE)
        solver.add(h_start >= 0, h_start <= MAX_SIZE)
        solver.add(v_start >= 0, v_start <= MAX_SIZE)

        solver.add(h_count + v_count > 0)

        in_w, out_w = Int(f"{id}_in_0_width"), Int(f"{id}_out_0_width")
        in_h, out_h = Int(f"{id}_in_0_height"), Int(f"{id}_out_0_height")

        solver.add(If(v_count == 0, out_w == in_w, And(
            v_start + (v_count - 1) * v_gap <= in_w,
            out_w == in_w + (v_count * v_width)
        )))

        solver.add(If(h_count == 0, out_h == in_h, And(
            h_start + (h_count - 1) * h_gap <= in_h, 
            out_h == in_h + (h_count * h_width)
        )))
