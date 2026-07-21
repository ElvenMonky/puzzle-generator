import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from typing import Any, Dict, Optional
from canvas import build_canvas, Geometry, CanvasSpec, GeometrySpec
from canvas_factory import build_factory, CanvasFactory, GeometryTemplateSpec, CanvasFactorySpec

def canvas_spec_from_factory(
    factory: CanvasFactory,
    rng: Optional[random.Random] = None
) -> CanvasSpec:
    size = factory.templates[factory.root].size
    # TODO: pick width and height based on size constraints
    width = size["width"]
    height = size["height"]
    root_geom = _extract_template(factory, factory.root, width, height, {}, rng, 0, 0)
    return {"width": width, "height": height, "geometries": [root_geom]}

def _extract_template(
    factory: CanvasFactory,
    template_name: str,
    width: int,
    height: int,
    overrides: Dict[str, Any],
    rng: random.Random,
    offset_x: int,
    offset_y: int
) -> GeometrySpec:
    tmpl = factory.templates[template_name]
    # Generate model for this template with the given dimensions
    model = factory.generate_model(template_name, width, height, rng)

    # Ensure group results are available
    if tmpl.group_results is None:
        tmpl.init_solver(factory.templates)

    child_geoms = []

    # Process each geometry group of the template
    for group, result in zip(tmpl.geometries, tmpl.group_results):
        cnt_val = model[result["cnt"]].as_long()
        for i in range(cnt_val):
            x = model[result["x"][i]].as_long()
            y = model[result["y"][i]].as_long()
            w = model[result["w"][i]].as_long()
            h = model[result["h"][i]].as_long()
            slot = result["slots"][i]  # GeometryReference

            # Determine effective template for this slot (fallback to group's template)
            slot_tmpl_name = slot.template if slot.template is not None else group.template
            if slot_tmpl_name is None:
                # No template – skip (should not happen in a well-formed spec)
                continue

            # Slot overrides (could include 'geometries', color, etc.)
            slot_overrides = slot.overrides.copy()

            # Recursively extract the child template
            child_geom = _extract_template(
                factory,
                slot_tmpl_name,
                w, h,
                slot_overrides,
                rng,
                offset_x + x,
                offset_y + y
            )

            # Apply slot's direction (if any) to the child's root shape
            eff_dir = slot.dir if slot.dir is not None else group.dir
            child_geom["dir"] = eff_dir

            # If slot overrides contain extra geometries (static specs), add them as children
            if "geometries" in slot_overrides:
                # The override geometries are assumed to be simple (no nested templates)
                extra = slot_overrides["geometries"]
                if isinstance(extra, list):
                    for g_spec in extra:
                        # Convert the spec to a GeometrySpec (it may be a dict)
                        # Here we assume it's already a valid GeometrySpec-like dict
                        # but we need to offset it relative to the child's origin.
                        # For simplicity, we offset all coordinates by (offset_x + x, offset_y + y)
                        # and keep the rest as is.
                        extra_geom = g_spec.copy()
                        extra_geom["x"] = extra_geom.get("x", 0) + offset_x + x
                        extra_geom["y"] = extra_geom.get("y", 0) + offset_y + y
                        child_geom["geometries"].append(extra_geom)

            child_geoms.append(child_geom)

    # Build the GeometrySpec for this template's own shape
    # Apply overrides to template properties
    eff_type = overrides.get("type", tmpl.type)
    eff_color = overrides.get("color", tmpl.color)
    eff_edge_color = overrides.get("edge_color", tmpl.edge_color)
    eff_vertice_color = overrides.get("vertice_color", tmpl.vertice_color)

    # Create vertices based on type and dimensions
    if eff_type == "Point":
        vertices = [(width // 2, height // 2)]
    elif eff_type == "None":
        vertices = []
    else:  # Rectangle, Polygon, default to rectangle
        vertices = [(0, 0), (width, 0), (width, height), (0, height)]

    geom_spec: GeometrySpec = {
        "x": offset_x,
        "y": offset_y,
        "dir": 0,  # will be overridden by parent if needed
        "vertices": vertices,
        "color": eff_color,
        "edge_color": eff_edge_color,
        "vertice_color": eff_vertice_color,
        "geometries": child_geoms,
    }
    return geom_spec

# ==========================================
# 1. SHARED CONSTANTS
# ==========================================
ARC_COLORS = [
    '#000000', '#0074D9', '#FF4136', '#2ECC40', '#FFDC00',
    '#AAAAAA', '#F012BE', '#FF851B', '#7FDBFF', '#870C25'
]
ARC_CMAP = ListedColormap(ARC_COLORS)

# ==========================================
# 8. EXECUTION
# ==========================================
if __name__ == "__main__":
    templates: dict[str, GeometryTemplateSpec] = {
        "macro_puzzles_grid": {
            "type": "Rectangle",
            "color": 5,
            "size": { "width": 47, "height": 47 },
            "geometries": [
                {
                    "count": 9,
                    "cols": { "count": 3 },
                    "gap": 1,
                    "strategy": "flow",
                    "link": {},
                    "template": "puzzle_item",
                    "prefix": [0, 1, 2, 3, 4, 5, 6, 7, 8],
                    "pool": [
                        {
                            "template": "puzzle_1"
                        },
                        {
                            "template": "puzzle_2"
                        },
                        {
                            "template": "puzzle_3"
                        },
                        {
                            "template": "puzzle_4"
                        },
                        {
                            "template": "puzzle_5"
                        }
                    ]
                }
            ]
        },
        "puzzle_item": {
            "color": 0,
            "size": { "width": 15, "height": 15 },
            "type": "Rectangle",
        },
        "puzzle_1": {
            "template": "puzzle_item",
            "geometries": [
                {
                    "count": [2, 4],
                    "gap": 1,
                    "strategy": "random",
                    "template": "puzzle_1_blob"
                }
            ]
        },
        "puzzle_1_blob": {
            "color": 1,
            "size": {"min": [3, 7], "max": [7, 11]},
            "type": "None",
            "geometries": [
                {
                    "count": [2, 5],
                    "gap": 1,
                    "link": {
                        "gap": [1, 3],
                        "color": 2
                    },
                    "size": {"min": [3, 5], "max": [3, 7]},
                    "strategy": "tree",
                    "template": "puzzle_1_blob_piece",
                    "prefix": [0],
                    "pool": [
                        {
                            "geometries": [
                                {
                                    "count": 1,
                                    "margin": 1,
                                    "template": "puzzle_1_blob_point"
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        "puzzle_1_blob_piece": {
            "size": {"min": [3, 5], "max": [3, 7]},
            "type": "Rectangle",
        },
        "puzzle_1_blob_point": {
            "type": "Point",
            "color": [3, 9]
        },
        "puzzle_2": {
            "template": "puzzle_item",
            "geometries": [
                {
                    "count": 9,
                    "cols": { "count": 3 },
                    "strategy": "flow",
                    "template": "puzzle_2_tile",
                    "tag": "the tile",
                    "row_pattern": [0,1],
                    "pool": [
                        { "dir": 0 },
                        { "dir": 12 }
                    ]
                }
            ]
        },
        "puzzle_2_tile": {
            "color": 9,
            "size": {
                "width": 5,
                "height": 5,
            },
            "type": "Rectangle",
            "geometries": [
                {
                    "count": [1, 5],
                    "gap": 1,
                    "strategy": "flow",
                    "template": "puzzle_2_mark"
                }
            ]
        },
        "puzzle_2_mark": {
            "type": "Rectangle",
            "size": {
                "width": 2,
                "height": 1,
            },
            "color": 3
        },
        "puzzle_3": {
            "template": "puzzle_item",
            "geometries": [
                {
                    "count": 9,
                    "margin": 1,
                    "gap": 1,
                    "strategy": "tree",
                    "levels": 1,
                    "pool": [
                        { "template": "puzzle_3_root" }
                    ],
                    "prefix": [0],
                    "pattern": [1],
                    "link": {
                        "gap": 3,
                        "color": 2,
                        "above": 1
                    },
                    "template": "puzzle_3_node"
                }
            ]
        },
        "puzzle_3_root": {
            "type": "Point",
            "color": [3, 8]
        },
        "puzzle_3_node": {
            "type": "Rectangle",
            "size": { "width": 3, "height": 3 },
            "color": 9
        },
        "puzzle_4": {
            "template": "puzzle_item",
            "geometries": [
                {
                    "count": [10, 20],
                    "margin": 1,
                    "gap": 0,
                    "strategy": "tree",
                    "template": "puzzle_4_point",
                }
            ]
        },
        "puzzle_4_point": {
            "type": "Point",
            "color": 9
        },
        "puzzle_5": {
            "template": "puzzle_item",
            "geometries": [
                {
                    "count": [2, 4],
                    "gap": 1,
                    "strategy": "random",
                    "template": "puzzle_5_item"
                }
            ]
        },
        "puzzle_5_item": {
            "color": -1,
            "size": {"min": [5, 7], "max": [5, 9]},
            "type": "Rectangle",
            "edge_color": 1,
            "vertice_color": 2,
            "cut": {"tl":0, "tr":[3,5], "br":0, "bl":[2,6,2]}
        }
    }
    spec: CanvasFactorySpec = {
        "root": "macro_puzzles_grid",
        "templates": templates
    }

    canvas_factory = build_factory(spec)
    canvas_spec = canvas_spec_from_factory(canvas_factory)
    print(canvas_spec)
    canvas = build_canvas(canvas_spec)
    grid_in = canvas.render()

    def fill_container(node: Geometry) -> Optional[int]:
        point_color = None
        polys = []
        geoms = node.geometries
        if len(geoms) == 1 and len(geoms[0].vertices) == 1:
            c = geoms[0].color
            del geoms[0]
            return c
        for g in geoms:
            if point_color is None:
                point_color = fill_container(g)
            if len(g.vertices) > 2:
                polys.append(g)
        if point_color is not None:
            for p in polys:
                p.fill_color = point_color
        return None

    for layer in canvas.layers:
        fill_container(layer)

    grid_out = canvas.render()

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    axes[0].imshow(grid_in, cmap=ARC_CMAP, vmin=0, vmax=9)
    axes[0].set_title("Input")
    axes[1].imshow(grid_out, cmap=ARC_CMAP, vmin=0, vmax=9)
    axes[1].set_title("Output")
    for ax in axes:
        ax.grid(True, color='#555', linewidth=1)
        ax.set_xticks(np.arange(-0.5, canvas.width, 1), [])
        ax.set_yticks(np.arange(-0.5, canvas.height, 1), [])
    plt.tight_layout()
    plt.savefig("rendering_example.png")
    print("Done. See rendering_example.png")
