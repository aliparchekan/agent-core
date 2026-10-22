"""Explicit model-facing units; native sessions and safety checks remain pixels."""

import math


def coordinate_scale(coordinate_system):
    """Reject unknown conventions rather than infer units from coordinate values."""
    return {"pixels": None, "normalized_1": 1, "normalized_1000": 1000}[coordinate_system]


def coordinate_guidance(coordinate_system):
    """One contract shared by the tool description and every pointer schema."""
    scale = coordinate_scale(coordinate_system)
    if scale is None:
        return "coordinate_system=pixels: use latest-image x in [0,width), y in [0,height)."
    return (
        f"coordinate_system={coordinate_system}: x and y are each in [0,{scale}), upper bound excluded. "
        f"Top-left is (0,0); image center is ({scale / 2:g},{scale / 2:g}). "
        "Use this grid for coordinates, control bounds and cursor; image width/height remain pixels."
    )


def pixel_action(action, observation, coordinate_system):
    """Convert once, after freshness validation and before binding an entire batch."""
    scale = coordinate_scale(coordinate_system)
    if scale is None or (action.x is None and not action.path):
        return action
    if observation is None or min(observation.width, observation.height) <= 0:
        raise ValueError("coordinates require a current screenshot with positive dimensions")

    def point(x, y):
        if not all(not isinstance(v, bool) and math.isfinite(v) and 0 <= v < scale for v in (x, y)):
            raise ValueError(coordinate_guidance(coordinate_system))
        return [x / scale * observation.width, y / scale * observation.height]

    update = {}
    if action.x is not None:
        update["x"], update["y"] = point(action.x, action.y)
    if action.path:
        update["path"] = [point(*pair) for pair in action.path]
    return action.model_copy(update=update)


def project_observation(observation, coordinate_system):
    """Project only the public result, never the worker observation or its evidence."""
    result = {**observation, "coordinate_system": coordinate_system}
    scale = coordinate_scale(coordinate_system)
    if scale is None:
        return result
    sx, sy = scale / observation["width"], scale / observation["height"]
    result["desktop_bounds"] = result.pop("bounds")
    result["elements"] = [
        {**element, "bounds": [v * s for v, s in zip(element["bounds"], (sx, sy, sx, sy))]}
        if "bounds" in element
        else dict(element)
        for element in observation["elements"]
    ]
    if observation.get("cursor") is not None:
        cursor = observation["cursor"]
        result["cursor"] = {**cursor, "x": cursor["x"] * sx, "y": cursor["y"] * sy}
    return result
