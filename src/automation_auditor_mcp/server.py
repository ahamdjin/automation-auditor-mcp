"""Official MCP Python SDK v2 entrypoint — stdio, no remote network calls."""
from __future__ import annotations

from mcp.server import MCPServer

from .core import audit_workflow as inspect, supported_platforms as platforms
from .integrations import audit_openapi as inspect_api, preflight_url as check_url

mcp = MCPServer("Automation Auditor MCP")


@mcp.tool()
def audit_workflow(platform: str, source: str) -> dict:
    """Read-only checks on n8n JSON, Dify DSL, Activepieces JSON or Trigger.dev code.

    platform: n8n | dify | activepieces | trigger | auto.
    Paste an export/source string; no filesystem access, no external calls, no execution.
    Trigger.dev findings are heuristic and not a substitute for TypeScript checks.
    """
    return inspect(platform, source)


@mcp.tool()
def audit_openapi(spec_json: str) -> dict:
    """Check an OpenAPI 3.x JSON spec for common tool integration mistakes.

    JSON only in this v1 tool. Not a full OpenAPI validation or a security audit.
    """
    return inspect_api(spec_json)


@mcp.tool()
def preflight_url(url: str) -> dict:
    """Evaluate syntax and literal IP red flags without fetching a URL.

    For domain names, request-time DNS and HTTP redirects remain unchecked.
    A manual_review result NEVER means safe to fetch.
    """
    return check_url(url)


@mcp.tool()
def list_supported_platforms() -> dict:
    """List exact export types and limitations; unsupported platforms are never called safe."""
    return platforms()


def main() -> None:
    mcp.run()  # stdio: the MCP client launches the process.


if __name__ == "__main__":
    main()
