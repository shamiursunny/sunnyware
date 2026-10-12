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
from .rag_search import RagSearchTool
from .rag_list import RagListTool
from .recall_history import RecallHistoryTool
from .csv_query import CsvQueryTool
from .chart_from_data import ChartFromDataTool
from .citation_lookup import CitationLookupTool
from .forecast_arima import ForecastArimaTool
from .financial_metrics import FinancialMetricsTool
from .api_call import ApiCallTool
from .document_diff import DocumentDiffTool
from .pdf_report import PdfReportTool
from .workspace_snapshot import WorkspaceSnapshotTool
from .excel_write import ExcelWriteTool


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
    RagSearchTool.name: RagSearchTool(),
    RagListTool.name: RagListTool(),
    RecallHistoryTool.name: RecallHistoryTool(),
    CsvQueryTool.name: CsvQueryTool(),
    ChartFromDataTool.name: ChartFromDataTool(),
    CitationLookupTool.name: CitationLookupTool(),
    ForecastArimaTool.name: ForecastArimaTool(),
    FinancialMetricsTool.name: FinancialMetricsTool(),
    ApiCallTool.name: ApiCallTool(),
    DocumentDiffTool.name: DocumentDiffTool(),
    PdfReportTool.name: PdfReportTool(),
    WorkspaceSnapshotTool.name: WorkspaceSnapshotTool(),
    ExcelWriteTool.name: ExcelWriteTool(),
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
