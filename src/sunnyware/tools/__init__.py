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
from .pdf_read import PdfReadTool
from .report_batch import ReportBatchTool
from .kpi_watch_add import KpiWatchAddTool
from .kpi_watch_list import KpiWatchListTool
from .kpi_watch_run import KpiWatchRunTool
from .email_send import EmailSendTool
from .email_list_sent import EmailListSentTool
from .email_configured import EmailConfiguredTool
from .url_metadata import UrlMetadataTool
from .html_to_text import HtmlToTextTool
from .data_quality_report import DataQualityReportTool
from .schedule_add import ScheduleAddTool
from .schedule_list import ScheduleListTool
from .schedule_delete import ScheduleDeleteTool
from .schedule_run_now import ScheduleRunNowTool
from .metrics_batch import MetricsBatchTool
from .webhook_add import WebhookAddTool
from .webhook_list import WebhookListTool
from .webhook_delete import WebhookDeleteTool
from .webhook_events import WebhookEventsTool
from .sql_sandbox_create import SqlSandboxCreateTool
from .sql_sandbox_execute import SqlSandboxExecuteTool
from .sql_sandbox_list import SqlSandboxListTool
from .sql_sandbox_load_csv import SqlSandboxLoadCsvTool
from .sql_sandbox_drop import SqlSandboxDropTool
from .workspace_snapshot import WorkspaceSnapshotTool
from .excel_write import ExcelWriteTool
from .excel_read import ExcelReadTool
from .browser_goto import BrowserGotoTool
from .browser_screenshot import BrowserScreenshotTool
from .browser_extract import BrowserExtractTool
from .browser_click import BrowserClickTool
from .browser_fill_submit import BrowserFillSubmitTool
from .image_generate import ImageGenerateTool


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
    PdfReadTool.name: PdfReadTool(),
    ReportBatchTool.name: ReportBatchTool(),
    KpiWatchAddTool.name: KpiWatchAddTool(),
    KpiWatchListTool.name: KpiWatchListTool(),
    KpiWatchRunTool.name: KpiWatchRunTool(),
    EmailSendTool.name: EmailSendTool(),
    EmailListSentTool.name: EmailListSentTool(),
    EmailConfiguredTool.name: EmailConfiguredTool(),
    UrlMetadataTool.name: UrlMetadataTool(),
    HtmlToTextTool.name: HtmlToTextTool(),
    DataQualityReportTool.name: DataQualityReportTool(),
    ScheduleAddTool.name: ScheduleAddTool(),
    ScheduleListTool.name: ScheduleListTool(),
    ScheduleDeleteTool.name: ScheduleDeleteTool(),
    ScheduleRunNowTool.name: ScheduleRunNowTool(),
    MetricsBatchTool.name: MetricsBatchTool(),
    WebhookAddTool.name: WebhookAddTool(),
    WebhookListTool.name: WebhookListTool(),
    WebhookDeleteTool.name: WebhookDeleteTool(),
    WebhookEventsTool.name: WebhookEventsTool(),
    SqlSandboxCreateTool.name: SqlSandboxCreateTool(),
    SqlSandboxExecuteTool.name: SqlSandboxExecuteTool(),
    SqlSandboxListTool.name: SqlSandboxListTool(),
    SqlSandboxLoadCsvTool.name: SqlSandboxLoadCsvTool(),
    SqlSandboxDropTool.name: SqlSandboxDropTool(),
    WorkspaceSnapshotTool.name: WorkspaceSnapshotTool(),
    ExcelWriteTool.name: ExcelWriteTool(),
    ExcelReadTool.name: ExcelReadTool(),
    BrowserGotoTool.name: BrowserGotoTool(),
    BrowserScreenshotTool.name: BrowserScreenshotTool(),
    BrowserExtractTool.name: BrowserExtractTool(),
    BrowserClickTool.name: BrowserClickTool(),
    BrowserFillSubmitTool.name: BrowserFillSubmitTool(),
    ImageGenerateTool.name: ImageGenerateTool(),
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
