from z3 import And, Int, If, Solver
from transformations.base import ARCTransformation, MAX_SIZE
from transformations.geometry import Split
from features.base import Line, MAX_FEATURES

class AddLines(ARCTransformation):
    config = {
        Line.__name__: {
            "min": 1,
            "max": MAX_FEATURES
        }
    }

    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str, pre_phase: bool, feature_types: set[str], feature_slots: list[tuple[int, int, int]]):
        super().register_variables_and_constraints(solver, id, pre_phase, feature_types, feature_slots)

        key = Line.__name__
        count = Int(f"{id}_{key}_count")
        dir = Int(f"{id}_param_direction")
        start = Int(f"{id}_param_start")
        width = Int(f"{id}_param_width")
        gap   = Int(f"{id}_param_gap")

        in_w, out_w = Int(f"{id}_in_0_width"), Int(f"{id}_out_0_width")
        in_h, out_h = Int(f"{id}_in_0_height"), Int(f"{id}_out_0_height")

        solver.add(dir >= 0, dir <= 1)
        solver.add(width > 0, gap > 0)

        solver.add(If(dir == 0, And(
            start + (count - 1) * gap <= in_h, 
            out_h == in_h + count * width
        ), And(
            start + (count - 1) * gap <= in_w,
            out_w == in_w + count * width
        )))

        for f_id in feature_ids:
            f_dir = Int(f"{id}_out_0_{f_id}_direction")
            f_start = Int(f"{id}_out_0_{f_id}_start")
            f_width = Int(f"{id}_out_0_{f_id}_width")
            f_index = Int(f"{f_id}_index")

            solver.add(f_index >= 0, f_index < count)

            solver.add(f_dir == dir)
            solver.add(f_start == start + gap * f_index)
            solver.add(f_width == width)


class SplitByLine(Split):
    config = {
        Line.__name__: {
            "min": -1,
            "max": -1
        }
    }

    @classmethod
    def register_variables_and_constraints(cls, solver: Solver, id: str, pre_phase: bool, feature_types: set[str], feature_slots: list[tuple[int, int, int]]):
        super().register_variables_and_constraints(solver, id, pre_phase, feature_types, feature_slots)
        
        direction = Int(f"{id}_param_direction")
        start = Int(f"{id}_param_start")
        width = Int(f"{id}_param_width")

        f_id = feature_ids[0]
        line_direction = Int(f"{id}_in_0_{f_id}_direction")
        line_start = Int(f"{id}_in_0_{f_id}_start")
        line_width = Int(f"{id}_in_0_{f_id}_width")

        solver.add(direction == line_direction)
        solver.add(start == line_start)
        solver.add(width == line_width)
