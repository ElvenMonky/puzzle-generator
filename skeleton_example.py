from time import time
from skeleton import Skeleton

# Mock Skeleton definition
skeleton = Skeleton(2, [
  { "type": "CreateCanvas", "in": [] },
  { "type": "AddLines", "in": [0], "features": [(-1, 0, 0, 1)] },
  { "type": "Rotate90", "in": [1], "features": [(0, 0, 0, 0)] },
  { "type": "Split", "in": [2], "features": [(0, 0, -1, 2)] },
  { "type": "Rotate90", "in": [(3, 1)] },
  { "type": "Tile", "in": [4] },
  { "type": "Upscale", "in": [3] },
  { "type": "Merge", "in": [5, 6] },
])

skeleton.validate()
