# evaluate_minicpm.py
import json
import asyncio
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sunnyware.jarvis_agent import find_relevant_tools, select_tool_via_local_llm

# The 18 cases where Needle 3 + Keyword failed (from v6 eval)
MINICPM_TARGETS = [
    "Use Python to calculate the first 10 fibonacci numbers.",
    "Query the data.csv file for all rows where the city is 'London'.",
    "Use csv_query to select all from sales.csv.",
    "Create a webhook named 'test_hook' pointing to https://mysite.com/hook.",
    "Schedule a task named 'daily_report' to run every 24 hours.",
    "Create a bar chart from the data [1, 2, 3, 4, 5].",
    "Calculate financial metrics for the prices [100, 102, 101, 105].",
    "Narrate this table: [[1, 2], [3, 4]].",
    "Run a data quality report on the dataset [[1, 2], [3, null]].",
    "Compare the two documents 'A' and 'B'.",
    "Convert the HTML '<b>Hello</b>' to plain text.",
    "Create a PDF report with the title 'Summary' and content 'Hello'.",
    "Write the data [1, 2, 3] to an Excel file named 'data.xlsx'.",
    "Add a KPI watch for 'website_traffic'.",
    "Set HITL to require confirmation for the 'calculator' tool.",
    "Recall our last 3 messages.",
    "What's the capital of France?",
    "What's the weather like on Mars?",
]

async def evaluate_minicpm():
    dataset_path = Path("golden_dataset.jsonl")
    if not dataset_path.exists():
        return {"error": "dataset not found"}

    # Load only the target cases
    all_entries = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            all_entries.append(json.loads(line))

    targets = [e for e in all_entries if e["prompt"] in MINICPM_TARGETS]
    print("[eval] Testing {} MiniCPM-target cases".format(len(targets)), flush=True)

    correct = 0
    no_call_correct = 0
    no_call_total = 0
    total = 0
    failures = []
    errors = []

    for entry in targets:
        total += 1
        prompt = entry["prompt"]
        expected = entry["expected_tool"]
        try:
            shortlist = await find_relevant_tools(prompt, top_k=15)
            result = await select_tool_via_local_llm(prompt, shortlist) if shortlist else None
            actual = result.get("tool") if result else None

            if expected is None:
                no_call_total += 1
                if actual is None:
                    no_call_correct += 1
                continue

            if actual == expected:
                correct += 1
                print("[PASS] " + expected + ": " + prompt[:50], flush=True)
            else:
                failures.append({"expected": expected, "actual": actual, "prompt": prompt})
                print("[FAIL] " + expected + " -> " + str(actual) + ": " + prompt[:50], flush=True)
        except Exception as e:
            print("[CASE ERROR] " + str(e), flush=True)
            traceback.print_exc()
            errors.append({"prompt": prompt, "error": str(e)})
            failures.append({"expected": expected, "actual": "ERROR", "prompt": prompt})

    tool_total = total - no_call_total
    tool_accuracy = correct / tool_total if tool_total > 0 else 0
    no_call_acc = no_call_correct / no_call_total if no_call_total > 0 else 0

    print("\n" + "="*60, flush=True)
    print(" MINICPM (on 18 target cases)", flush=True)
    print("="*60, flush=True)
    print("Tool Accuracy: {:.2%} ({}/{})".format(tool_accuracy, correct, tool_total), flush=True)
    print("Case Errors: {}".format(len(errors)), flush=True)

    return {
        "tool_accuracy": tool_accuracy,
        "no_call_accuracy": no_call_acc,
        "failures": failures,
        "errors": errors,
    }
