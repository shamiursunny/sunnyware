# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Tool registry — all agent tools live in this package."""

from .echo import EchoTool
from .current_time import CurrentTimeTool
from .read_file import ReadFileTool
from .write_file import WriteFileTool
from .calculator import CalculatorTool
from .web_fetch import WebFetchTool
from .memory_search import MemorySearchTool
from .web_search import WebSearchTool
from .weather import WeatherTool
from .date_calc import DateCalcTool
from .python_eval import PythonEvalTool
from .list_files import ListFilesTool
from .delete_file import DeleteFileTool
from .mkdir import MkdirTool


_TOOLS = {
    EchoTool.name: EchoTool(),
    CurrentTimeTool.name: CurrentTimeTool(),
    ReadFileTool.name: ReadFileTool(),
    WriteFileTool.name: WriteFileTool(),
    CalculatorTool.name: CalculatorTool(),
    WebFetchTool.name: WebFetchTool(),
    MemorySearchTool.name: MemorySearchTool(),
    WebSearchTool.name: WebSearchTool(),
    WeatherTool.name: WeatherTool(),
    DateCalcTool.name: DateCalcTool(),
    PythonEvalTool.name: PythonEvalTool(),
    ListFilesTool.name: ListFilesTool(),
    DeleteFileTool.name: DeleteFileTool(),
    MkdirTool.name: MkdirTool(),
}


def list_tools() -> list:
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        }
        for t in _TOOLS.values()
    ]


def get_tool(name: str):
    return _TOOLS.get(name)


def tool_names() -> list:
    return list(_TOOLS.keys())
