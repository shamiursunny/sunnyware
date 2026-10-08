# Sunnyware MCP Server

Sunnyware exposes all 14 tools + a virtual agent_query tool via the
Model Context Protocol (JSON-RPC 2.0).

## Transports

### 1. HTTP JSON-RPC (hosted on HF)

- Info:  GET  https://shamiur-sunnyware.hf.space/mcp
- RPC:   POST https://shamiur-sunnyware.hf.space/mcp/rpc

### 2. stdio (local, for Claude Desktop)

- Runner: python H:/sunnyware/scripts/mcp_stdio.py

## Claude Desktop Setup

Edit ~/AppData/Roaming/Claude/claude_desktop_config.json to add:

  "mcpServers": {
    "sunnyware": {
      "command": "python",
      "args": ["H:/sunnyware/scripts/mcp_stdio.py"]
    }
  }

Then restart Claude Desktop.

## Tools exposed

14 native tools + 1 virtual agent_query tool.

## Protocol methods

- initialize
- tools/list
- tools/call
- resources/list (empty)
- prompts/list (empty)
- ping

## Example: initialize

curl -s -X POST https://shamiur-sunnyware.hf.space/mcp/rpc -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

## Example: call weather

curl -s -X POST https://shamiur-sunnyware.hf.space/mcp/rpc -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"weather","arguments":{"city":"Dhaka"}}}'

## Example: agent_query

curl -s -X POST https://shamiur-sunnyware.hf.space/mcp/rpc -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"agent_query","arguments":{"input":"What is 2+2?"}}}'
