import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from typing import Optional

from canvas_instance import build_canvas, Geometry, Point, Polygon
from canvas_template import generate_instance_spec, CanvasTemplateSpec

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
    spec: CanvasTemplateSpec = {
        "width": 31,
        "height": 31,
        "background": 5,
        "geometries": [
            {
                "count": 4,
                "gap": 1,
                "size": { "width": 15, "height": 15 },
                "strategy": "flow",
                "type": "Rectangle",
                "color": 0,
                "prefix": [0, 1, 2, 3],
                "pool": [
                    {
                        "geometries": [
                            {
                                "color": 1,
                                "count": [2, 4],
                                "gap": 1,
                                "size": {"min": [3, 7], "max": [7, 11]},
                                "strategy": "random",
                                "type": "Geometry",
                                "geometries": [
                                    {
                                        "count": [2, 5],
                                        "gap": 1,
                                        "link": {
                                            "type": ["Line", "Diagonal"],
                                            "gap": [1, 3],
                                            "color": 2
                                        },
                                        "size": {"min": [3, 5], "max": [3, 7]},
                                        "strategy": "tree",
                                        "type": "Rectangle",
                                        "geometries": [
                                            {
                                                "type": "Point",
                                                "count": [0, 1],
                                                "color": [3, 9],
                                                "margin": 1
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "geometries": [
                            {
                                "color": 9,
                                "count": 9,
                                "size": {
                                    "width": 5,
                                    "height": 5,
                                },
                                "strategy": "flow",
                                "type": "Rectangle",
                                "geometries": [
                                    {
                                        "type": "Rectangle",
                                        "size": {
                                            "width": 2,
                                            "height": 1,
                                        },
                                        "gap": 1,
                                        "strategy": "flow",
                                        "count": [1, 5],
                                        "color": 3
                                    }
                                ],
                                "pattern": [0,1],
                                "pool": [
                                    {"dir": 0, "singleton": True },
                                    {"dir": 4 }
                                ]
                            }
                        ]
                    },
                    {
                        "geometries": [
                            {
                                "color": 9,
                                "count": 9,
                                "margin": 1,
                                "gap": 1,
                                "strategy": "tree",
                                "levels": 1,
                                "pool": [
                                    { "type": "Point", "color": [3, 8] },
                                    { "type": "Rectangle", "size": { "width": 3, "height": 3 } }
                                ],
                                "prefix": [0],
                                "pattern": [1],
                                "link": {
                                    "type": ["Line", "Diagonal"],
                                    "gap": 3,
                                    "color": 2,
                                    "above": 1
                                }
                            }
                        ]
                    },
                    {
                        "geometries": [
                            {
                                "color": 9,
                                "count": [10, 20],
                                "margin": 1,
                                "gap": 0,
                                "strategy": "tree",
                                "type": "Point",
                            }
                        ]
                    },
                    {
                        "geometries": [
                            {
                                "color": 1,
                                "count": [2, 4],
                                "gap": 1,
                                "size": {"min": [5, 7], "max": [5, 9]},
                                "strategy": "random",
                                "type": "Rectangle",
                                "fill_color": -1,
                                "vertice_color": 2,
                                "cut": {"tl":0, "tr":[3,5], "br":0, "bl":[2,6,2]}
                            }
                        ]
                    },
                ],
            },
        ]
    }

    instance_spec = generate_instance_spec(spec)
    print(instance_spec)
    canvas = build_canvas(instance_spec)
    grid_in = canvas.render()

    def fill_container(node: Geometry) -> Optional[int]:
        point_color = None
        polys = []
        geoms = node.geometries
        if len(geoms) == 1 and isinstance(geoms[0], Point):
            c = geoms[0].color
            geoms[0].color = -1
            return c
        for g in geoms:
            if point_color is None:
                point_color = fill_container(g)
            if isinstance(g, Polygon):
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
        ax.set_xticks(np.arange(-0.5, instance_spec['width'], 1), [])
        ax.set_yticks(np.arange(-0.5, instance_spec['height'], 1), [])
    plt.tight_layout()
    plt.savefig("rendering_example.png")
    print("Done. See rendering_example.png")
