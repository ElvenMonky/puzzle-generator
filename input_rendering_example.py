import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from typing import Optional
from canvas import build_canvas, Geometry, CanvasSpec, GeometrySpec
from canvas_factory import build_factory, CanvasFactory, CanvasFactorySpec, CutSpec, GeometryGroup, GeometryReference, GeometryTemplateSpec
from size_and_range import roll_range

def canvas_spec_from_factory(factory: CanvasFactory, rng: Optional[random.Random] = None) -> CanvasSpec:
    rng = rng or random.Random()
    root_size = factory.templates[factory.root].size
    width = roll_range(root_size.get("width", 1), rng)
    height = roll_range(root_size.get("height", 1), rng)
    root_geom = _extract_template(factory, factory.root, width // 2, height // 2, width, height, rng)
    return {"width": width, "height": height, "geometries": [root_geom]}

def corner_points(ox: int, oy: int, w: int, h: int, cuts: CutSpec) -> list[tuple[int, int]]:
    tl, tr, br, bl = cuts["tl"], cuts["tr"], cuts["br"], cuts["bl"]
    raw = []
    raw.append((ox + tl, oy))
    raw.append((ox + w - 1 - tr, oy))
    if tr: raw.append((ox + w - 1, oy + tr))
    raw.append((ox + w - 1, oy + h - 1 - br))
    if br: raw.append((ox + w - 1 - br, oy + h - 1))
    raw.append((ox + bl, oy + h - 1))
    if bl: raw.append((ox, oy + h - 1 - bl))
    if tl: raw.append((ox, oy + tl))

    pts = []
    for p in raw:
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) > 1 and pts[-1] == pts[0]:
        pts.pop()
    return pts

def _extract_group_items(factory: CanvasFactory, group: GeometryGroup, model, px: int, py: int, rng: random.Random) -> list[GeometrySpec]:
    result = group.result
    items = []
    cnt_val = model[result["cnt"]].as_long()
    for i in range(cnt_val):
        x = model[result["x"][i]].as_long()
        y = model[result["y"][i]].as_long()
        w = model[result["w"][i]].as_long()
        h = model[result["h"][i]].as_long()
        slot_val = model[result["slot"][i]].as_long()

        ref: Optional[GeometryReference] = None
        template_name = group.template
        if 0 <= slot_val < len(group.pool):
            ref = group.pool[slot_val]
            template_name = ref.template if ref.template is not None else group.template
        if template_name is None:
            continue

        ox = w // 2
        oy = h // 2
        if ref is not None and ref.origin is not None:
            if ref.origin.x:
                ox = roll_range(ref.origin.x)
            if ref.origin.y:
                oy = roll_range(ref.origin.y)
        child = _extract_template(factory, template_name, ox, oy, w, h, rng)
        child["x"] = x + ox - px
        child["y"] = y + oy - py
        dir_spec = ref.dir if ref is not None and ref.dir is not None else group.dir
        child["dir"] = roll_range(dir_spec, rng)

        if ref is not None:
            extra_groups = ref.overrides.get("geometries", [])
            if extra_groups:
                extra_models = ref.generate_child_models(w, h, rng)
                for extra_group, extra_model in zip(extra_groups, extra_models):
                    child["geometries"].extend(_extract_group_items(factory, extra_group, extra_model, ox, oy, rng))

        items.append(child)
    return items

def _extract_template(factory: CanvasFactory, template_name: str, x: int, y: int, width: int, height: int,
                       rng: random.Random) -> GeometrySpec:
    tmpl = factory.templates[template_name]
    models = factory.generate_child_models(template_name, width, height, rng)

    child_geoms = []
    for group, model in zip(tmpl.geometries, models):
        child_geoms.extend(_extract_group_items(factory, group, model, x, y, rng))

    color = roll_range(tmpl.color, rng) if tmpl.color is not None else None
    edge_color = roll_range(tmpl.edge_color, rng) if tmpl.edge_color is not None else None
    vertice_color = roll_range(tmpl.vertice_color, rng) if tmpl.vertice_color is not None else None

    vertices = []
    if tmpl.type == "Point":
        vertices = [(0, 0)]
    elif tmpl.type == "Polygon":
        cut_vals: CutSpec = { "tr": 0, "tl": 0, "br": 0, "bl": 0 }
        if tmpl.cut is not None:
            model = tmpl.generate_model(width, height, rng)
            cut_vals = {k: model[v].as_long() for k, v in tmpl.result.items()}
        vertices = corner_points(-x, -y, width, height, cut_vals)

    return {
        "x": x, "y": y, "dir": 0,
        "vertices": vertices,
        "color": color,
        "edge_color": edge_color,
        "vertice_color": vertice_color,
        "geometries": child_geoms,
    }

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
            "type": "Polygon",
            "color": 5,
            "size": {"width": 47, "height": 47},
            "geometries": [
                {
                    "count": 9,
                    "gap": 1,
                    "template": "puzzle_item",
                    "link": { "cols": { "count": 3 } },
                    "prefix": [0, 1, 2, 3, 4, 5, 6, 7, 8],
                    "pool": [
                        {"template": "puzzle_1"},
                        {"template": "puzzle_2"},
                        {"template": "puzzle_3"},
                        {"template": "puzzle_4"},
                        {"template": "puzzle_5"},
                    ],
                }
            ],
        },
        "puzzle_item": {
            "type": "Polygon",
            "color": 0,
            "size": {"width": 15, "height": 15},
        },
        "puzzle_1": {
            "template": "puzzle_item",
            "geometries": [
                {
                    "count": [2, 4],
                    "gap": 1,
                    "template": "puzzle_1_blob"
                }
            ],
        },
        "puzzle_1_blob": {
            "type": "None",
            "color": 1,
            "size": {"min": [3, 7], "max": [7, 11]},
            "geometries": [
                {
                    "count": [2, 5],
                    "gap": 1,
                    "template": "puzzle_1_blob_piece",
                    "link": {"order": "dfs", "dir": [0, 7]},
                    "prefix": [0],
                    "pattern": [-1],
                    "pool": [
                        {
                            "size": {"min": [3, 5], "max": [3, 7]},
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
            ],
        },
        "puzzle_1_blob_piece": {
            "type": "Polygon",
            "color": 2,
            "size": {"min": [2, 5], "max": [3, 7]},
        },
        "puzzle_1_blob_point": {
            "type": "Point",
            "color": [3, 9],
            "size": {"width": 1, "height": 1},
        },
        "puzzle_2": {
            "template": "puzzle_item",
            "geometries": [
                {
                    "count": 9,
                    "link": { "cols": { "count": 3 } },
                    "template": "puzzle_2_tile",
                    "tag": "the tile",
                    "pattern": [0],
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
            "type": "Polygon",
            "geometries": [
                {
                    "count": [1, 5],
                    "gap": 1,
                    "link": {},
                    "template": "puzzle_2_mark"
                }
            ]
        },
        "puzzle_2_mark": {
            "type": "Polygon",
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
                    "count": [4, 9],
                    "gap": 1,
                    "margin": 1,
                    "pool": [{"template": "puzzle_3_root"}],
                    "prefix": [0],
                    "pattern": [1],
                    "template": "puzzle_3_node",
                    "link": {"order": "bfs", "dir": [0, 7], "root_dir": [0, 7]},
                    
                }
            ],
        },
        "puzzle_3_root": {
            "type": "Point",
            "color": [3, 8]
        },
        "puzzle_3_node": {
            "type": "Polygon",
            "color": 9,
            "size": {"width": 3, "height": 3},
        },
        "puzzle_4": {
            "template": "puzzle_item",
            "geometries": [
                {
                    "count": [10, 20],
                    "margin": 1,
                    "gap": 0,
                    "template": "puzzle_4_point",
                    "link": {"order": "rng"},
                    "pool": [{"template": "puzzle_4_point"}],
                }
            ],
        },
        "puzzle_4_point": {
            "type": "Point",
            "color": 9,
            "size": {"width": 1, "height": 1},
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
            "type": "Polygon",
            "edge_color": 1,
            "vertice_color": 2,
            "cut": {"tl":0, "tr":[3,5], "br":0, "bl":[2,6,2]}
        }
    }
    spec: CanvasFactorySpec = {
        "root": "macro_puzzles_grid",
        "templates": templates,
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
                p.edge_color = p.color
                p.color = point_color
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
