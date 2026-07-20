import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from typing import Optional

from canvas import build_canvas, Geometry
from canvas_factory import build_factory, CanvasFactorySpec

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
    spec: CanvasFactorySpec = {
        "macro_puzzles_grid": {
            "type": "Rectangle",
            "color": 5,
            "size": { "width": 47, "height": 47 },
            "geometries": [
                {
                    "count": 9,
                    "cols": 3,
                    "gap": 1,
                    "strategy": "flow",
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
                    "cols": 3,
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

    canvas_factory = build_factory(spec)
    root_model = canvas_factory.generate_model("macro_puzzles_grid", 47, 47)
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
