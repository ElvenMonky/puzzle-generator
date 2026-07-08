import graphviz
from time import time
from typing import TypedDict, Optional
from z3 import Int, ModelRef, Solver, sat
from transformations import ARCTransformation
from features import ARCFeature

InputRef = int | tuple[int, int]

TransformationRef = TypedDict('TransformationRef', {
    'type': str,
    'in': list[InputRef],
    'criteria': Optional[list[str]],
    'feature_ids': Optional[list[str]]
})

class Skeleton:
    def __init__(self, input: InputRef, items: list[TransformationRef] = []):
        self.items = items
        self.input = input

    def validate(self):
        solver = Solver()
        input_index, _ = (self.input, 0) if isinstance(self.input, int) else self.input

        feature_types: set[str] = set()
        for step in self.items:
            ARCTransformation.REGISTRY[step["type"]].register_features(feature_types)

        for index, step in enumerate(self.items):
            id = f"v{index}"
            feature_slots = step.get("features", [])
            ARCTransformation.REGISTRY[step["type"]].register_variables_and_constraints(solver, id, index <= input_index, feature_types, feature_slots)
            for in_index, ref in enumerate(step["in"]):
                sk_index, out_index = (ref, 0) if isinstance(ref, int) else ref
                other_id = f"v{sk_index}"
                for prop in ["width", "height"]:
                    solver.add(Int(f"{other_id}_out_{out_index}_{prop}") == Int(f"{id}_in_{in_index}_{prop}"))
                for key in feature_types:
                    solver.add(Int(f"{other_id}_{key}_out_{out_index}_count") == Int(f"{id}_{key}_in_{in_index}_count"))
            for in_wire, index, _ in feature_slots:
                if in_wire >= 0:
                    ref = step["in"][in_wire]
                    sk_index, out_wire = (ref, 0) if isinstance(ref, int) else ref
                    other_id = f"v{sk_index}"
                    for prop in ["type", "x", "y", "width", "height", "color", "mask"]:
                        in_var = Int(f"{id}_in_{in_wire}_{index}_{prop}")
                        out_var = Int(f"{other_id}_out_{out_wire}_{index}_{prop}")
                        solver.add(in_var == out_var)

        start = time()
        result = solver.check()
        print(f"Solve time: {time() - start:.4f}s")
        print(solver.statistics())

        if result == sat:
            model = solver.model()
            print("Skeleton successfully resolved! Here are the computed parameters:")
            
            # Extract the concrete integer values from the model
            # model.decls() gives us every variable the solver touched
            for d in model.decls():
                print(f"  {d.name()} = {model[d].as_long()}")

            self.graph(model)
        else:
            print("Skeleton is structurally impossible! The solver proved no valid configuration exists.")

    def graph(self, model: ModelRef, filename="sample_skeleton"):
        """Generates a visual flowchart of the solved DAG using Graphviz."""
        
        # Initialize a directed graph
        dot = graphviz.Digraph(comment='ARC Puzzle Skeleton', format='png')
        dot.attr(rankdir='TB', size='8,10') # Top-to-Bottom layout
        
        # 1. Create the Nodes with Parameter Summaries
        for index, step in enumerate(self.items):
            node_id = f"v{index}"
            node_type = step["type"]
            
            # Extract internal parameters from the Z3 model for this node
            params = []
            for d in model.decls():
                if d.name().startswith(f"{node_id}_param_"):
                    param_name = d.name().replace(f"{node_id}_param_", "")
                    params.append(f"{param_name}: {model[d].as_long()}")
                    
            param_str = "\\n".join(params)
            label = f"{node_id}: {node_type}" + (f"\\n---\\n{param_str}" if param_str else "")
            
            # Create a visually distinct box for the node
            dot.node(node_id, label, shape='box', style='filled', fillcolor='lightgrey')
            
        # 2. Draw the Edges with Dimensional Data
        for index, step in enumerate(self.items):
            node_id = f"v{index}"
            
            for in_index, ref in enumerate(step.get("in", [])):
                src_index, out_index = (ref, 0) if isinstance(ref, int) else ref
                src_id = f"v{src_index}"

                # Query Z3 to find out exactly what size grid is passing through this wire
                try:
                    w = model.evaluate(Int(f"{src_id}_out_{out_index}_width")).as_long()
                    h = model.evaluate(Int(f"{src_id}_out_{out_index}_height")).as_long()
                    wire_label = f"{w}x{h}"
                except AttributeError:
                    wire_label = "unknown"
                
                # Connect the nodes and label the wire with the grid size
                dot.edge(src_id, node_id, label=wire_label)
                
        # Render and save the file
        dot.render(filename, view=True)
        print(f"Graph rendered and saved to {filename}.png")
