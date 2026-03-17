from .creation import CREATION_TOOLS, handle_creation_tool
from .discovery import DISCOVERY_TOOLS, handle_discovery_tool
from .execution import EXECUTION_TOOLS, handle_execution_tool
from .utility import UTILITY_TOOLS, handle_utility_tool

ALL_TOOLS = DISCOVERY_TOOLS + CREATION_TOOLS + EXECUTION_TOOLS + UTILITY_TOOLS

TOOL_HANDLERS = {
    **{t.name: handle_discovery_tool for t in DISCOVERY_TOOLS},
    **{t.name: handle_creation_tool for t in CREATION_TOOLS},
    **{t.name: handle_execution_tool for t in EXECUTION_TOOLS},
    **{t.name: handle_utility_tool for t in UTILITY_TOOLS},
}
