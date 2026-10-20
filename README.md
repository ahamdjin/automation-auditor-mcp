# Automation Auditor MCP

**One MCP server, several real automation export formats.** Built and maintained by [Ahmad Yar](https://www.ahmadyar.co/).

<!-- mcp-name: io.github.ahamdjin/automation-auditor-mcp -->

This project is a **starter implementation**. It has not been published to PyPI or registered in the MCP Registry, and its MCP transport has not yet been end-to-end tested against a host. It performs read-only static checks on supplied text; it never reads your repo on its own, contacts automation accounts, runs JS, or connects to API endpoints.

## Supported inputs and honest limitations

| Platform | Input | Checks | Boundary |
| --- | --- | --- | --- |
| **n8n** | Exported workflow JSON | Missing/duplicate node names or IDs, broken connections, missing webhook paths | Static structure; no credential or live execution checks |
| **Dify** | Exported workflow DSL YAML/JSON | Missing or duplicate node IDs, broken edges, start/end checks | YAML DSL varies with releases; no runtime/model validation |
| **Trigger.dev** | Source of task definitions (TypeScript/JS) | Literal task IDs, duplicates, advisory duration notes | **Heuristics only**; run TypeScript and Trigger.dev build/tests |
| **Activepieces** | Flow JSON or flow version object | Trigger presence, duplicate step names, invalid-marked steps | Common nextAction/branches only; not an exhaustive flow validator |
| **OpenAPI** | JSON spec | Existing [GPT Tools](https://github.com/ahamdjin/ahmad-yar-automation-lab) integration checker | Best effort, not complete OpenAPI schema validation |
| **URL preflight** | HTTPS URL | Known unsafe URL schemes/addresses using GPT Tools | No DNS or fetch. "manual_review" is not "safe." |

**"Any automation platform" is not possible without an adapter for its native format.** Unsupported platforms are reported as unsupported, rather than passing a meaningless check. You can add adapters to the registry in `core.py` and corresponding tests. Make, Zapier and Pipedream are not advertised as supported in v0.1.

## Install locally (after publishing to PyPI)

Install with Python 3.11+:

    pip install automation-auditor-mcp

Configure a compatible MCP client:

```json
{
  "mcpServers": {
    "automation-auditor": {
      "command": "uvx",
      "args": ["automation-auditor-mcp"]
    }
  }
}
```

`uvx` requires `uv`. The package and command are **not published yet**, so this configuration is illustrative until the PyPI release succeeds.

For development from source:

    python -m pip install -e .
    python -m unittest discover -s tests -v
    automation-audit examples/n8n-valid.json --platform n8n
    automation-auditor-mcp

The last command runs the MCP stdio server and waits for a connected client. Use a host or MCP Inspector to communicate with it; starting from an ordinary terminal should not print output.

## MCP tool API

- `audit_workflow(platform, source)`: Pass the full **text contents** of an export or Trigger.dev source file. `platform` is `auto`, `n8n`, `dify`, `trigger`, `trigger.dev`, or `activepieces`. Max 250,000 characters. The server does **not** read files by path.
- `audit_openapi(spec_json)`: JSON OpenAPI document; uses the existing `ahmad-yar-gpt-tools` library.
- `preflight_url(url)`: Pure URL screening; never performs DNS lookup or HTTP request. A permitted syntax becomes `manual_review` because real fetching requires request-time controls.
- `list_supported_platforms()`: Exact supported formats and known limitations.

Findings include a stable rule ID, severity, location, brief message, recommendation and confidence. They intentionally do **not** echo node names, raw URLs, credentials or source snippets. A report of `no_findings_detected` is **not** proof of safety.

## Example: detect a broken n8n connection

The MCP client passes exported workflow JSON to `audit_workflow("n8n", source)`. If a connection points to a deleted node, the structured report includes rule `N8N009` with severity `error`. The assistant can explain the error and request the user to fix it. This tool never edits workflow files itself.

## Tests

    python -m unittest discover -s tests -v

Test fixtures use only fictional metadata; no API keys or customer information. The core format inspectors require no network and do not import MCP at test time; MCP SDK integration requires installing dependencies.

## Publishing checklist (do not publish before live testing)

1. Create public GitHub repo `ahamdjin/automation-auditor-mcp` and push these sources.
2. Run all tests and check MCP Inspector tool calls in a real MCP client. Improve Trigger.dev analysis with a TypeScript AST parser before describing it as comprehensive.
3. Build and release a distribution on [PyPI](https://pypi.org/). For trusted publishing, configure your PyPI publisher correctly; package publishing requires a separate approval/credentials step.
4. Preserve the README marker `mcp-name: io.github.ahamdjin/automation-auditor-mcp` **inside the PyPI long description** for Registry package ownership verification.
5. Generate and validate `server.json` using the [official MCP Registry publisher](https://github.com/modelcontextprotocol/registry); set the PyPI package identifier/version and stdio transport. Log in using GitHub, then publish.
6. Verify the listing by querying the official Registry API. The Registry hosts metadata, not your package.

The Registry's [official publishing requirements](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx) explain PyPI ownership verification.

## Security, licensing and attribution

No source content is intentionally stored, sent externally, executed, or used for model inference. The MCP host may log inputs or reports separately. YAML aliases are refused, duplicate JSON/YAML fields are rejected, and input size is bounded. Trigger.dev regex checks have low confidence; a source audit cannot guarantee runtime behavior. Never treat URL preflight as SSRF prevention.

**License:** Apache-2.0. Upstream `ahmad-yar-gpt-tools` also uses Apache-2.0.

Source (after repository creation): https://github.com/ahamdjin/automation-auditor-mcp
Creator: https://www.ahmadyar.co/
