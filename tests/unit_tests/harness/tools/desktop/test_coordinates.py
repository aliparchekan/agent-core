"""Coordinate contracts are independent of applications, model names and layouts."""

from dataclasses import asdict, replace

import pytest
from pydantic import ValidationError

from openjiuwen.core.session.agent import Session
from openjiuwen.harness.tools.desktop.coordinates import pixel_action, project_observation
from openjiuwen.harness.tools.desktop.direct import DirectDesktopSession
from openjiuwen.harness.tools.desktop.direct_protocol import input_schema
from openjiuwen.harness.tools.desktop.direct_tool import DirectComputerUseTool
from openjiuwen.harness.tools.desktop.schema import Action, DesktopSettings, Observation
from tests.unit_tests.harness.tools.desktop.test_direct import Desktop, Lease


def image(width=800, height=500):
    return Observation("aW1hZ2U=", width, height, (-200, 40, 400, 250), "test", 1, 1)


@pytest.mark.parametrize("units,scale", [("normalized_1", 1), ("normalized_1000", 1000)])
@pytest.mark.parametrize("size", [(800, 500), (701, 901), (1280, 720), (1, 1)])
@pytest.mark.parametrize("kind", ["move", "click", "hold_mouse", "scroll", "drag"])
def test_all_pointer_actions_map_the_actual_image_then_native_geometry(units, scale, size, kind):
    observation = image(*size)
    fields = {"path": [[0, 0], [scale / 4, scale / 2]]} if kind == "drag" else {"x": scale / 4, "y": scale / 2}
    action = Action(kind=kind, **fields)
    converted = pixel_action(action, observation, units)
    point = converted.path[-1] if kind == "drag" else (converted.x, converted.y)
    assert point == pytest.approx((size[0] / 4, size[1] / 2))
    assert observation.point(*point) == pytest.approx((-100, 165))
    assert action.model_dump(exclude_defaults=True) == {"kind": kind, **fields}


@pytest.mark.parametrize("value", [-1, 1000, 1001, float("nan"), float("inf"), True, "500"])
@pytest.mark.parametrize("kind", ["click", "drag"])
def test_invalid_coordinates_are_rejected_without_clamping(value, kind):
    with pytest.raises((ValueError, ValidationError)):
        action = Action(kind=kind, **({"path": [[0, 0], [value, 10]]} if kind == "drag" else {"x": value, "y": 10}))
        pixel_action(action, image(), "normalized_1000")


def test_pixel_default_and_non_pointer_actions_are_unchanged():
    assert DesktopSettings().coordinate_system == "pixels"
    with pytest.raises(ValidationError):
        DesktopSettings(coordinate_system="auto")
    for action in (Action(kind="click", x=1, y=1), Action(kind="type", text="hello"), Action(kind="scroll")):
        assert pixel_action(action, image(), "pixels") is action
    assert pixel_action(Action(kind="click", x=1, y=1), image(), "normalized_1000").x == 0.8


def test_projection_keeps_native_state_and_pixel_dimensions():
    observation = asdict(
        replace(
            image(),
            elements=[{"id": "e", "bounds": [80, 50, 160, 100]}],
            cursor={"x": 400, "y": 250},
            context={"geometry": {"desktop_rect": {"x": -200}}},
        )
    )
    projected = project_observation(observation, "normalized_1000")
    assert projected["elements"][0]["bounds"] == [100, 100, 200, 200]
    assert projected["cursor"] == {"x": 500, "y": 500}
    assert projected["width"] == 800 and projected["height"] == 500
    assert projected["desktop_bounds"] == (-200, 40, 400, 250)
    assert projected["context"] == observation["context"]
    assert observation["elements"][0]["bounds"] == [80, 50, 160, 100]
    assert observation["cursor"]["x"] == 400 and "coordinate_system" not in observation
    schema = input_schema(coordinate_system="normalized_1000")["properties"]
    assert "normalized_1000" in schema["x"]["description"]
    assert "normalized_1000" in schema["actions"]["items"]["properties"]["path"]["description"]


@pytest.mark.asyncio
@pytest.mark.parametrize("batched", [False, True])
async def test_tool_conversion_is_after_freshness_before_batch_binding(batched):
    settings = DesktopSettings(
        enabled=True, targets=[{"name": "test", "pid": 99999}], coordinate_system="normalized_1000"
    )
    desktop, lease = Desktop(), Lease()
    original = desktop.observe

    async def capture():
        current = await original()
        return replace(
            current,
            width=800,
            height=500,
            elements=[
                {
                    "id": str(current.generation),
                    "role": "AXButton",
                    "label": "Control",
                    "enabled": True,
                    "actionable": True,
                    "bounds": [390, 240, 20, 20],
                }
            ],
        )

    desktop.observe = capture
    state = DirectDesktopSession(settings, driver_factory=lambda _: desktop, lease_factory=lambda: lease)
    tool = DirectComputerUseTool(settings, session_factory=lambda: state)
    try:
        first = await tool.invoke({"operation": "observe"}, session=Session("owner"))
        token = first.data["observation_id"]
        assert first.data["observation"]["coordinate_system"] == "normalized_1000"
        for supplied, x in [("stale", 500), (token, 1000)]:
            call = {"operation": "click", "x": x, "y": 500}
            payload = (
                {"operation": "batch", "actions": [{"operation": "type", "text": "unchanged"}, call]}
                if batched
                else call
            )
            rejected = await tool.invoke({**payload, "observation_id": supplied}, session=Session("owner"))
            assert not rejected.success and not desktop.actions and state.token == token
        call = {"operation": "click", "x": 500, "y": 500}
        payload = {"operation": "batch", "actions": [{"operation": "type", "text": "hello"}, call]} if batched else call
        result = await tool.invoke(
            {**payload, "observation_id": token, "release_after": True}, session=Session("owner")
        )
        assert result.success and result.data["closed"]
        assert (desktop.actions[-1].x, desktop.actions[-1].y) == (400, 250)
        assert state.observation.elements[0]["bounds"] == [390, 240, 20, 20]
        assert lease.released
    finally:
        await tool.close()
