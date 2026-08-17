import json
import os
from google.adk import Agent

CATALOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "schemas", "field_layout_tracker", "asset_catalog.json"
)

with open(CATALOG_PATH) as f:
    ASSET_CATALOG = json.load(f)


def search_catalog(query: str) -> str:
    """Search the Field Layout Tracker asset catalog by name, category, or type.

    Use this BEFORE place_asset whenever the user describes an item in plain
    language (e.g. "outlet", "30 inch sink base", "shower") instead of giving
    an exact catalog code. Returns up to 8 best matches with their code, name,
    category, and type so you can pick the right one.

    Args:
        query: A search term, e.g. "outlet" or "sink base".

    Returns:
        A JSON string list of matching catalog items.
    """
    q = query.lower()
    matches = [
        item for item in ASSET_CATALOG
        if q in item["name"].lower() or q in item.get("category", "").lower() or q in item["code"].lower()
    ]
    return json.dumps(matches[:8])


def set_tool(tool: str) -> dict:
    """Switch the active drawing tool on the canvas.

    Args:
        tool: One of "select", "wall", "door", "window", "rect_select".

    Returns:
        The action payload to send to the app.
    """
    return {"function": "setTool", "args": {"tool": tool}}


def place_asset(code: str) -> dict:
    """Arm the place-asset tool with a specific catalog item, so the user can
    click the canvas to drop it in. Always resolve the correct code via
    search_catalog first unless the user gave you an exact code already.

    Args:
        code: The exact catalog code, e.g. "OUT" or "B36".

    Returns:
        The action payload to send to the app.
    """
    return {"function": "place_asset", "args": {"code": code}}


def undo() -> dict:
    """Undo the last action taken in the app."""
    return {"function": "undo", "args": {}}


def redo() -> dict:
    """Redo the last undone action."""
    return {"function": "redo", "args": {}}


def save_project() -> dict:
    """Save the current project."""
    return {"function": "save", "args": {}}


root_agent = Agent(
    name="field_layout_tracker_agent",
    model="gemini-3.6-flash",
    instruction=(
        "You are CRACKER, an action controller for the Field Layout Tracker app. "
        "You NEVER chat or explain yourself. Your only job is to translate the "
        "user's command into exactly one final tool call: set_tool, place_asset, "
        "undo, redo, or save_project. "
        "If the user wants to place an item and you don't have its exact catalog "
        "code, call search_catalog first, pick the single best match, then call "
        "place_asset with that code. "
        "Never ask the user a clarifying question -- pick the single best "
        "interpretation and act. After calling the action tool, respond with a "
"single short word like 'Done.' -- never leave your final response empty."
    ),
    tools=[search_catalog, set_tool, place_asset, undo, redo, save_project],
