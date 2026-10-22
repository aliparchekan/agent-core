"""State hints clarify focus boundaries without choosing or executing an action."""

import copy
import json

import pytest

from openjiuwen.core.foundation.tool.schema import ToolOutput
from openjiuwen.harness.tools.desktop.direct_tool import DirectComputerUseTool
from openjiuwen.harness.tools.desktop.schema import DesktopSettings


@pytest.mark.parametrize(
    "active,closed,windows,expected",
    [
        (None, False, [{"window_id": "shared-a"}], True),
        ("shared-a", False, [{"window_id": "shared-a"}], False),
        (None, True, [{"window_id": "shared-a"}], False),
        (None, False, [], False),
    ],
)
def test_focus_hint_uses_only_returned_scope(active, closed, windows, expected):
    tool = DirectComputerUseTool(DesktopSettings(enabled=True, targets=[{"name": "editor", "pid": 99999}]))
    data = {"closed": closed, "observation": {"context": {"active_window_id": active, "windows": windows}}}
    before = copy.deepcopy(data)
    rendered = json.loads(tool.render_for_llm(ToolOutput(success=True, data=data)))
    assert ("input_instruction" in rendered) is expected
    assert data == before and tool._state is None
    if expected:
        assert "SEPARATE call" in rendered["input_instruction"]
        assert "shared-a" not in rendered["input_instruction"]


@pytest.mark.parametrize("limit", [2, 4, 8])
def test_batch_guidance_matches_configured_limit(limit):
    tool = DirectComputerUseTool(
        DesktopSettings(
            enabled=True,
            targets=[{"name": "editor", "pid": 99999}],
            max_batch_actions=limit,
        )
    )
    assert f"at most {limit} actions" in tool.card.description
    batch = tool.card.input_params["properties"]["actions"]
    assert f"at most {limit}" in batch["description"]
    assert batch["maxItems"] == limit
