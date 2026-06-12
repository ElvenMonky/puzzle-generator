import graphviz
from z3 import Int, ModelRef
from transformations import Skeleton

def visualize_skeleton(skeleton: Skeleton, model: ModelRef, filename="sample_skeleton"):
    """Generates a visual flowchart of the solved DAG using Graphviz."""
    
    # Initialize a directed graph
    dot = graphviz.Digraph(comment='ARC Puzzle Skeleton', format='png', filename=f'{filename}.dot')
    dot.attr(rankdir='TB', size='8,10') # Top-to-Bottom layout
    
    # 1. Create the Nodes with Parameter Summaries
    for index, step in enumerate(skeleton):
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
    for index, step in enumerate(skeleton):
        node_id = f"v{index}"
        
        for in_index, ref in enumerate(step.get("in", [])):
            # Parse the skeleton connection notation
            if isinstance(ref, int):
                src_index, out_index = ref, 0
            else:
                src_index, out_index = ref[0], ref[1]
                
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