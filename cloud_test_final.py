import urllib.request
import json

url = "https://shamiur-sunnyware.hf.space/api/tools-test-all"
req = urllib.request.Request(url, method="POST", data=b"{}")
req.add_header("Content-Type", "application/json")
req.add_header("x-api-key", "master-admin-key")

print("Calling cloud endpoint (timeout 900s)...")
try:
    with urllib.request.urlopen(req, timeout=900) as response:
        data = json.loads(response.read().decode("utf-8"))
        s = data.get("summary", {})
        print("")
        print("=== CLOUD SUMMARY ===")
        print("  Total:    " + str(s.get('total')))
        print("  Passed:   " + str(s.get('passed')))
        print("  Failed:   " + str(s.get('failed')))
        print("  Skipped:  " + str(s.get('skipped')))

        print("")
        print("=== CLOUD FAILURES ===")
        fails = [r for r in data.get("results", []) if r["status"] == "FAIL"]
        if not fails:
            print("  (none)")
        for r in fails:
            print("  " + r['name'] + ": " + r['error'][:150])

        print("")
        print("=== TESTED FILE TOOLS ===")
        tested = ['generate_chart', 'csv_groupby', 'generate_report', 'ml_forecast', 'pro_chart', 'csv_query', 'chart_from_data', 'forecast_arima', 'data_quality_report']
        for r in data.get("results", []):
            if r['name'] in tested:
                status = r['status']
                detail = r['error'] if status == 'FAIL' else r['output']
                print(f"  {r['name']}: {status} ({r['latency_ms']}ms) {str(detail)[:80]}")

except urllib.error.HTTPError as e:
    print("HTTP Error " + str(e.code) + ": " + str(e.reason))
    print(e.read().decode("utf-8", errors="replace")[:300])
except Exception as e:
    print("Error: " + str(e))
