# evaluate_needle.py
import json
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sunnyware.tools import _TOOLS
from sunnyware.needle_tool_loader import build_schema_from_tool
from sunnyware.needle_router import try_needle_route
from sunnyware.jarvis_agent import find_relevant_tools

async def evaluate():
    dataset_path = Path("golden_dataset.jsonl")
    if not dataset_path.exists():
        print("[ERROR] golden_dataset.jsonl not found.", flush=True)
        return {"error": "dataset missing"}

    tool_selection_correct = 0
    no_call_correct = 0
    no_call_total = 0
    arg_scores = []
    total_cases = 0
    failures = []
    rag_misses = 0

    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            prompt = entry["prompt"]
            expected_tool = entry["expected_tool"]
            expected_args = entry.get("expected_args", {})
            total_cases += 1

            # STEP 1: Run RAG shortlist (exactly like production)
            shortlist = await find_relevant_tools(prompt, top_k=20)
            shortlist_names = [t.get("name") for t in shortlist] if shortlist else []
            
            # Check if expected tool is even in the shortlist
            rag_includes_expected = expected_tool in shortlist_names if expected_tool else True
            if expected_tool and not rag_includes_expected:
                rag_misses += 1
                print(f"[RAG_MISS] {expected_tool} not in shortlist: {shortlist_names}", flush=True)

            # STEP 2: Run Needle 3 on the shortlist
            result = None
            if shortlist:
                result = await try_needle_route(prompt, shortlist)
            
            actual_tool = result.get("tool") if result else None
            actual_args = result.get("args", {}) if result else {}

            # No-call cases
            if expected_tool is None:
                no_call_total += 1
                if actual_tool is None:
                    no_call_correct += 1
                    print(f"[PASS] NO-CALL: {prompt[:50]}", flush=True)
                else:
                    failures.append({
                        "prompt": prompt,
                        "expected": "NO CALL",
                        "actual_tool": actual_tool,
                        "actual_args": actual_args,
                        "reason": "False positive"
                    })
                    print(f"[FAIL] NO-CALL: {prompt[:50]} -> {actual_tool}", flush=True)
                continue

            # Tool selection
            if actual_tool == expected_tool:
                tool_selection_correct += 1
                total_keys = len(expected_args)
                if total_keys > 0:
                    correct_keys = sum(1 for k, v in expected_args.items() if k in actual_args and actual_args[k] == v)
                    arg_scores.append(correct_keys / total_keys)
                else:
                    arg_scores.append(1.0)
                print(f"[PASS] {expected_tool}: {prompt[:50]}", flush=True)
            else:
                failures.append({
                    "prompt": prompt,
                    "expected_tool": expected_tool,
                    "expected_args": expected_args,
                    "actual_tool": actual_tool,
                    "actual_args": actual_args,
                    "shortlist": shortlist_names,
                    "rag_includes_expected": rag_includes_expected,
                    "reason": f"Wrong tool (got {actual_tool})"
                })
                arg_scores.append(0.0)
                print(f"[FAIL] {expected_tool}: {prompt[:50]} -> {actual_tool}", flush=True)

    tool_cases_total = total_cases - no_call_total
    tool_accuracy = tool_selection_correct / tool_cases_total if tool_cases_total > 0 else 0
    no_call_accuracy = no_call_correct / no_call_total if no_call_total > 0 else 0
    avg_arg_f1 = sum(arg_scores) / len(arg_scores) if arg_scores else 0

    print("\n" + "="*60, flush=True)
    print(" EVALUATION RESULTS", flush=True)
    print("="*60, flush=True)
    print(f"Total Cases: {total_cases}", flush=True)
    print(f"Tool Selection Accuracy: {tool_accuracy:.2%} ({tool_selection_correct}/{tool_cases_total})", flush=True)
    print(f"Argument F1 Score: {avg_arg_f1:.2%}", flush=True)
    print(f"No-Call Accuracy: {no_call_accuracy:.2%} ({no_call_correct}/{no_call_total})", flush=True)
    print(f"RAG Misses: {rag_misses} (expected tool not in shortlist)", flush=True)
    print("="*60, flush=True)

    if failures:
        print(f"\n--- FAILURES ({len(failures)}) ---", flush=True)
        for f in failures:
            print(json.dumps(f), flush=True)

    return {
        "total": total_cases,
        "tool_accuracy": tool_accuracy,
        "arg_f1": avg_arg_f1,
        "no_call_accuracy": no_call_accuracy,
        "rag_misses": rag_misses,
        "failures": failures
    }
