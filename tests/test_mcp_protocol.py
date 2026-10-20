"""Real MCP stdio integration: spawn installed CLI and invoke published tools."""

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


class MCPProtocolSmokeTests(unittest.TestCase):
    def test_protocol_lists_and_calls_real_tools(self):
        async def check():
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "automation_auditor_mcp.server"],
                env=os.environ.copy(),
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = {t.name for t in tools.tools}
                    self.assertEqual(names, {
                        "audit_workflow", "audit_openapi", "preflight_url",
                        "list_supported_platforms",
                    })
                    for tool in tools.tools:
                        self.assertTrue(tool.description)
                        self.assertIn("type", tool.input_schema)

                    payload = (ROOT / "examples" / "n8n-broken.json").read_text(
                        encoding="utf-8"
                    )
                    result = await session.call_tool("audit_workflow", arguments={
                        "platform": "n8n", "source": payload
                    })
                    self.assertFalse(result.is_error)
                    output = result.structured_content
                    if not output:
                        output = json.loads(result.content[0].text)
                    self.assertEqual(output["platform"], "n8n")
                    self.assertIn("N8N009", {f["rule"] for f in output["findings"]})

                    details = await session.call_tool("list_supported_platforms", arguments={})
                    self.assertFalse(details.is_error)
                    catalog = details.structured_content
                    if not catalog:
                        catalog = json.loads(details.content[0].text)
                    self.assertIn("dify", catalog["native_adapters"])

                    url = await session.call_tool("preflight_url", arguments={
                        "url": "http://127.0.0.1/admin"
                    })
                    self.assertFalse(url.is_error)
                    answer = url.structured_content
                    if not answer:
                        answer = json.loads(url.content[0].text)
                    self.assertEqual(answer["decision"], "block")
        asyncio.run(asyncio.wait_for(check(), timeout=30))


if __name__ == "__main__":
    unittest.main()
