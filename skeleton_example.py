from time import time
from skeleton import Skeleton
from criteria.base import PositionCriteria

# Mock Skeleton definition
skeleton = Skeleton(2, [
  { "type": "CreateCanvas", "in": [] },
  { "type": "AddLines", "in": [0], "feature_ids": ["line_0"] },
  { "type": "Rotate90", "in": [1], "feature_ids": ["line_0"] },
  { "type": "Split", "in": [2], "criteria": [PositionCriteria.__name__], "feature_ids": ["line_0"] },
  { "type": "Rotate90", "in": [(3, 1)] },
  { "type": "Tile", "in": [4] },
  { "type": "Upscale", "in": [3] },
  { "type": "Merge", "in": [5, 6] },
])

skeleton.validate()
