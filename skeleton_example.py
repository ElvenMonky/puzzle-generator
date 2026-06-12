import random
from z3 import Int, Solver, sat
from transformations import REGISTRY

# Mock Skeleton definition
skeleton = [
  { "type": "Canvas", "in": [] },
  { "type": "Dummy", "in": [0] },
  { "type": "AddGridLines", "in": [1] },
  { "type": "Split", "in": [2] },
  { "type": "Dummy", "in": [(3, 1)] },
  { "type": "Tile", "in": [4] },
  { "type": "Upscale", "in": [3] },
  { "type": "Merge", "in": [5, 6] },
]

solver = Solver()

for index, step in enumerate(skeleton):
    id = f"v{index}"
    REGISTRY[step["type"]].register_variables_and_constraints(solver, id)
    for in_index, ref in enumerate(step["in"]):
        match ref:
            case int():
                sk_index, out_index = ref, 0
            case _:
                sk_index, out_index = ref[0], ref[1]
        other_step = skeleton[sk_index]
        other_id = f"v{sk_index}"
        for prop in ["width", "height"]:
            solver.add(Int(f"{other_id}_out_{out_index}_{prop}") == Int(f"{id}_in_{in_index}_{prop}"))

if solver.check() == sat:
    model = solver.model()
    print("Skeleton successfully resolved! Here are the computed parameters:")
    
    # Extract the concrete integer values from the model
    # model.decls() gives us every variable the solver touched
    for d in model.decls():
        print(f"  {d.name()} = {model[d].as_long()}")
else:
    print("Skeleton is structurally impossible! The solver proved no valid configuration exists.")