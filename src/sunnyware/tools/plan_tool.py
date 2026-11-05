from . import get_tool

class ExecutePlanTool:
    name = "execute_plan"
    description = "Execute a multi-step plan by running a sequence of tools. Pass a JSON array of steps, where each step has a 'tool' and 'args'."
    keywords = ["execute plan", "multi step", "run sequence", "execute tasks"]
    parameters = {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "description": "List of steps to execute. Each step is an object with 'tool' (the tool name) and 'args' (a dictionary of arguments).",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"}
                    },
                    "required": ["tool", "args"]
                }
            }
        },
        "required": ["steps"]
    }

    async def run(self, steps: list) -> dict:
        results = []
        for i, step in enumerate(steps):
            tool_name = step.get("tool")
            args = step.get("args", {})
            
            tool = get_tool(tool_name)
            if not tool:
                results.append({"step": i+1, "tool": tool_name, "error": f"Tool '{tool_name}' not found"})
                continue
                
            try:
                # Execute the tool
                res = await tool.run(**args)
                results.append({"step": i+1, "tool": tool_name, "result": res})
                
                # If a step fails (returns an error dict), stop the plan to prevent cascading failures
                if isinstance(res, dict) and res.get("error"):
                    results.append({"status": "halted", "reason": f"Step {i+1} failed: {res['error']}"})
                    break
            except Exception as e:
                results.append({"step": i+1, "tool": tool_name, "error": str(e)})
                results.append({"status": "halted", "reason": f"Exception in step {i+1}"})
                break

        return {
            "ok": True,
            "steps_executed": len(results),
            "results": results
        }
