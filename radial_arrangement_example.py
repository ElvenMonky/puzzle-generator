import numpy as np
import matplotlib.pyplot as plt
from arrangement import RadialArrangement

SIZE = (21, 21)
ORIGIN = (10, 10)

CONFIGS = {
    "star (4 rays, no turn)": dict(
        ray_starts=[(i, 0) for i in range(8)],
        turn_pattern=[],
    ),
    "pinwheel (45°/3, no growth)": dict(
        ray_starts=[(0, 3), (2, 3), (4, 3)],
        turn_pattern=[1],
    ),
    "archimedean spiral (90°/1, +1 every other turn)": dict(
        ray_starts=[(0, 2)],
        turn_pattern=[2],
        growth_pattern=[0, 2],
        gap_pattern=[0, 0, 2]
    ),
    "galaxy (4 arms, 45°/2, +1 growth)": dict(
        ray_starts=[(1, 1), (3, 1), (5, 1), (7, 1)],
        turn_pattern=[1],
        growth_pattern=[1],
    ),
    "overlapping spiral (crossing arms)": dict(
        ray_starts=[(0, 2), (4, 2)],
        turn_pattern=[2],
        growth_pattern=[0, 4],
        count=50
    ),
    "random order lightning star": dict(
        ray_starts=[(0, 2), (2, 2), (4, 2), (6, 2)],
        turn_prefix=[1],
        turn_pattern=[-2, 2],
        ray_selection="random",
        seed=1,
    ),
    "flow (fork_prefix, straight-to-wall)": dict(
        ray_starts=[(2, 0)],
        turn_prefix=[-2],
        fork_prefix=[1],
        ray_selection="same",
        count=50,
    ),
    "random walk": dict(
        ray_starts=[(0, 2)],
        turn_pattern=[-2, 0, 2],
        turn_mode="random",
    ),
    "random walk with skip": dict(
        ray_starts=[(0, 2), (4, 2)],
        turn_pattern=[-2, 0, 2],
        turn_mode="random",
        collision_mode="skip",
    ),
}

fig, axes = plt.subplots(3, 3, figsize=(20, 20))

for ax, (title, kwargs) in zip(axes.flat, CONFIGS.items()):
    cells = RadialArrangement(size=SIZE, origin=ORIGIN, **kwargs).generate()
    xs, ys = zip(*cells)
    ax.scatter(xs, ys, c=range(len(cells)), cmap="viridis", s=200)
    ax.set_title(title, fontsize=9)
    ax.set_xticks(np.arange(-0.5, SIZE[0], 1), [])
    ax.set_yticks(np.arange(-0.5, SIZE[1], 1), [])
    ax.set_aspect("equal")
    ax.invert_yaxis()

for ax in axes.flat[len(CONFIGS):]:
    ax.axis("off")

fig.tight_layout()
fig.savefig("radial_arrangement_deck.png")
