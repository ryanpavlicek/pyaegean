# aegean.mcp_server

The `aegean-mcp` Model Context Protocol server (the `[mcp]` extra): it exposes the toolkit's
read/analysis surface to agents as MCP tools. The tool functions are plain, JSON-returning
callables; `build_server` registers them with FastMCP (imported lazily, so `import aegean`
never pulls the MCP SDK).

::: aegean.mcp_server
