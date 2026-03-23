"""Entry-point for running the MCP server as a module.

    python -m mcp_server              # uses MCP_PORT env var (default 9000)

The SSE server will be reachable at http://0.0.0.0:<MCP_PORT>/sse
"""
from mcp_server.server import mcp

if __name__ == "__main__":
    mcp.run(transport="sse")
