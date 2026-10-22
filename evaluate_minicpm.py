# evaluate_minicpm.py
import json
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sunnyware.tools import _TOOLS
from sunnyware.jarvis_agent import find_relevant_tools, select_tool_via_local_llm

async def evaluate_minicpm():
    dataset_path = Path("golden_dataset.jsonl")
    if not dataset_path.exists():
        print("[ERROR] golden_dataset.jsonl not found", flush=True)
        return

    correct = 0
    total = 0
    no_call_correct = 0
    no_call_total = 0
    failures = []

    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            prompt = entry["prompt"]
            expected = entry["expected_tool"]
            total += 1
            shortlist = await find_relevant_tools(prompt, top_k=15)
            if not shortlist:
                result = None
            else:
                result = await select_tool_via_local_llm(prompt, shortlist)
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

    tool_total = total - no_call_total
    tool_accuracy = correct / tool_total if tool_total > 0 else 0
    no_call_acc = no_call_correct / no_call_total if no_call_total > 0 else 0

    print("\n" + "="*60, flush=True)
    print(" MINICPM ALONE", flush=True)
    print("="*60, flush=True)
    print("Tool Accuracy: {:.2%} ({}/{})".format(tool_accuracy, correct, tool_total), flush=True)
    print("No-Call Accuracy: {:.2%}".format(no_call_acc), flush=True)
    print("Total Failures: {}".format(len(failures)), flush=True)
    return {"tool_accuracy": tool_accuracy, "no_call_accuracy": no_call_acc, "failures": failures}
