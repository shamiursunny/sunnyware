# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 98 smoke test - Pollinations image generation tool."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 98: Pollinations image generation tool ===")

# 1. Tool file exists and parses
tool_path = SRC / "tools" / "image_generate.py"
check("tools/image_generate.py exists", tool_path.is_file())
tool_src = tool_path.read_text(encoding="utf-8") if tool_path.is_file() else ""
try:
    ast.parse(tool_src)
    check("image_generate.py parses", True)
except SyntaxError as e:
    check("image_generate.py parses", False, str(e))

# 2. Class + name + parameters
check("ImageGenerateTool class defined", "class ImageGenerateTool:" in tool_src)
check('name = "image_generate"', 'name = "image_generate"' in tool_src)
check("prompt parameter required", '"required": True' in tool_src)
for param in ["prompt", "model", "width", "height", "seed"]:
    check(f"parameter '{param}' declared", f'"{param}":' in tool_src)

# 3. Uses Pollinations free endpoint
check("uses image.pollinations.ai",
      "image.pollinations.ai" in tool_src)
check("has POLLINATIONS_IMAGE_BASE_URL override",
      "POLLINATIONS_IMAGE_BASE_URL" in tool_src)
check("URL-encodes prompt safely", "quote(prompt" in tool_src)

# 4. Returns base64 (same contract as chart_from_data)
check("returns image_base64", '"image_base64"' in tool_src)
check("returns image_format", '"image_format"' in tool_src)
check("detects JPEG magic bytes", 'b"\\xff\\xd8\\xff"' in tool_src or "b'\\xff\\xd8\\xff'" in tool_src)
check("detects PNG magic bytes", "PNG" in tool_src)

# 5. Registry
init_src = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("imported in tools/__init__.py",
      "from .image_generate import ImageGenerateTool" in init_src)
check("registered in _TOOLS dict",
      "ImageGenerateTool.name: ImageGenerateTool()" in init_src)

# 6. Live import check
sys.path.insert(0, str(SRC.parent))  # src/ -- parent of package
try:
    from sunnyware import tools as tr
    names = tr.tool_names()
    check("tool_names() includes image_generate", "image_generate" in names)
    check("total tools now 59+", len(names) >= 59, f"{len(names)} tools")
    tool = tr.get_tool("image_generate")
    check("get_tool('image_generate') returns instance", tool is not None)
    if tool:
        check("tool has .run coroutine", hasattr(tool, "run"))
        check("tool has .parameters dict", isinstance(tool.parameters, dict))
except Exception as e:
    check("live import works", False, f"{type(e).__name__}: {e}")

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    print("\nFAILED CHECKS:")
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
