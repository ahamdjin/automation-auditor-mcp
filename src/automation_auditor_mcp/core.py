"""Read-only, bounded static analysis on provided workflow/export content.

The platform adapter is explicit: unknown formats never produce a clean/pass result.
Structured findings deliberately avoid echoing raw input, secrets and node labels.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Callable
import re

MAX_SOURCE_CHARS = 250_000
MAX_FINDINGS = 100


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    location: str
    message: str
    recommendation: str
    confidence: str = "high"


def finding(rule: str, severity: str, location: str, message: str, recommendation: str, confidence: str = "high") -> Finding:
    return Finding(rule, severity, location, message, recommendation, confidence)


def _check(source: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Workflow source must be non-empty text")
    if len(source) > MAX_SOURCE_CHARS:
        raise ValueError(f"Workflow source exceeds the {MAX_SOURCE_CHARS} character limit")
    return source


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("JSON contains duplicate keys")
        result[k] = v
    return result


def _strict_json(source: str) -> Any:
    return json.loads(source, object_pairs_hook=_no_duplicates,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid JSON number")))


def _yaml(source: str) -> Any:
    try:
        import yaml
    except ImportError:
        raise ValueError("Dify YAML parsing requires PyYAML") from None

    class StrictLoader(yaml.SafeLoader):
        def compose_node(self, parent, index):
            if self.check_event(yaml.AliasEvent):
                raise ValueError("YAML aliases are not supported")
            return super().compose_node(parent, index)

    def construct_map(loader, node):
        pairs = loader.construct_pairs(node, deep=True)
        return _no_duplicates(pairs)

    StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_map)
    try:
        return yaml.load(source, Loader=StrictLoader)
    except yaml.YAMLError:
        raise ValueError("Invalid YAML syntax") from None


def _auto(source: str) -> str | None:
    stripped = source.lstrip()
    if re.search(r'(?:\btask|\bschemaTask|\bschedules\.task)\s*\(\s*\{', source) and (
        "@trigger.dev/sdk" in source or "trigger.dev/sdk" in source
    ):
        return "trigger"
    try:
        data = _strict_json(source) if stripped.startswith(("{", "[")) else _yaml(source)
    except (ValueError, TypeError, RecursionError, ImportError):
        return None
    if isinstance(data, dict):
        if isinstance(data.get("nodes"), list) and isinstance(data.get("connections"), dict):
            return "n8n"
        if isinstance(data.get("workflow"), dict) and isinstance(data["workflow"].get("graph"), dict):
            return "dify"
        if isinstance(data.get("version"), dict) and "trigger" in data["version"]:
            return "activepieces"
        if isinstance(data.get("trigger"), dict) and "nextAction" in data["trigger"]:
            return "activepieces"
    return None


def _summary(platform: str, findings: list[Finding], supported: bool = True) -> dict:
    errors = sum(f.severity == "error" for f in findings)
    warnings = sum(f.severity == "warning" for f in findings)
    return {
        "platform": platform,
        "supported": supported,
        # Never name a no-findings report "safe" or "secure".
        "status": "unsupported" if not supported else
                  ("findings" if findings else "no_findings_detected"),
        "summary": {"errors": errors, "warnings": warnings, "total": len(findings)},
        "findings": [asdict(f) for f in findings[:MAX_FINDINGS]],
        "truncated_findings": max(0, len(findings) - MAX_FINDINGS),
        "disclaimer": "Static, best-effort checks only; not a runtime test or security certification.",
    }


def audit_workflow(platform: str, source: str) -> dict:
    """Inspect supplied code or workflow exports; never read files or call APIs."""
    content = _check(source)
    name = platform.lower().strip() if isinstance(platform, str) else ""
    allowed = {"auto", "n8n", "dify", "trigger", "trigger.dev", "activepieces"}
    if name not in allowed:
        return _summary(name or "unknown", [finding(
            "GEN001", "info", "input", "No adapter is registered for this platform.",
            "Use one of: n8n, dify, trigger, activepieces; contribute a new adapter."
        )], False)
    if name == "auto":
        name = _auto(content) or "unknown"
        if name == "unknown":
            return _summary(name, [finding(
                "GEN002", "info", "input", "Could not identify a supported platform export.",
                "Pass the platform explicitly or provide the native export format."
            )], False)
    if name == "trigger.dev":
        name = "trigger"

    try:
        if name == "trigger":
            return _summary(name, audit_trigger(content))
        obj = _strict_json(content) if content.lstrip().startswith(("{", "[")) else _yaml(content)
        # Register new platform-specific adapters here (never silently fall back).
        adapters: dict[str, Callable[[Any], list[Finding]]] = {
            "n8n": audit_n8n,
            "dify": audit_dify,
            "activepieces": audit_activepieces,
        }
        if name in adapters:
            return _summary(name, adapters[name](obj))
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        # Never interpolate input into errors; exceptions can include source snippets.
        return _summary(name, [finding("GEN003", "error", "input",
            "Invalid or unsupported workflow document.", "Supply a valid export or source file.")])
    return _summary(name, [], False)


def audit_n8n(data: Any) -> list[Finding]:
    fs: list[Finding] = []
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list) or not isinstance(data.get("connections"), dict):
        return [finding("N8N001", "error", "root",
                        "Not an n8n JSON workflow export.",
                        "Export the workflow JSON from n8n.")]
    names: dict[str, int] = {}
    ids: set[str] = set()
    for i, node in enumerate(data["nodes"]):
        path = f"nodes[{i}]"
        if not isinstance(node, dict):
            fs.append(finding("N8N002", "error", path, "Node is not an object.", "Repair the exported node."))
            continue
        name = node.get("name")
        if not isinstance(name, str) or not name.strip():
            fs.append(finding("N8N003", "error", path, "Node has no valid name.", "Assign a unique node name."))
        else:
            if name in names:
                fs.append(finding("N8N004", "error", path, "Duplicate node name.", "Give each node a unique name."))
            names[name] = i
        ident = node.get("id")
        if isinstance(ident, str) and ident:
            if ident in ids:
                fs.append(finding("N8N005", "error", path, "Duplicate node ID.", "Regenerate the duplicate ID."))
            ids.add(ident)
        typ = node.get("type", "")
        if isinstance(typ, str) and typ.lower().endswith(".webhook"):
            params = node.get("parameters") or {}
            if not isinstance(params, dict) or not params.get("path"):
                fs.append(finding("N8N006", "warning", path, "Webhook path is missing.",
                                  "Configure an explicit webhook path."))
    for source, channels in data["connections"].items():
        source_index = names.get(source)
        if source_index is None:
            fs.append(finding("N8N007", "error", "connections",
                              "Connection references a missing source node.", "Repair the source connection."))
        if not isinstance(channels, dict):
            fs.append(finding("N8N008", "error", "connections",
                              "Connection channel must be a mapping.", "Re-export the workflow."))
            continue
        for outputs in channels.values():
            if not isinstance(outputs, list):
                continue
            for connections in outputs:
                if not isinstance(connections, list):
                    continue
                for item in connections:
                    if isinstance(item, dict) and item.get("node") not in names:
                        fs.append(finding("N8N009", "error", f"nodes[{source_index}]" if source_index is not None else "connections",
                                          "Connection targets a missing node.", "Reconnect the destination node."))
    return fs


def audit_dify(data: Any) -> list[Finding]:
    if not isinstance(data, dict) or not isinstance(data.get("workflow"), dict):
        return [finding("DFY001", "error", "root", "Not a Dify workflow DSL export.",
                        "Export the workflow YAML from Dify Studio.")]
    graph = data["workflow"].get("graph")
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        return [finding("DFY002", "error", "workflow.graph", "Dify node/edge graph is missing.",
                        "Export the full Dify application DSL.")]
    fs: list[Finding] = []
    ids: set[str] = set()
    starts, ends = 0, 0
    for i, node in enumerate(graph["nodes"]):
        if not isinstance(node, dict):
            fs.append(finding("DFY003", "error", f"nodes[{i}]", "Node is not an object.", "Repair the Dify graph."))
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            fs.append(finding("DFY004", "error", f"nodes[{i}]", "Node has no ID.", "Assign a unique ID."))
        elif node_id in ids:
            fs.append(finding("DFY005", "error", f"nodes[{i}]", "Duplicate node ID.", "Replace duplicate IDs."))
        else:
            ids.add(node_id)
        d = node.get("data") or {}
        node_type = d.get("type", node.get("type", "")) if isinstance(d, dict) else ""
        if node_type == "start":
            starts += 1
        if node_type in {"end", "answer"}:
            ends += 1
    if starts < 1:
        fs.append(finding("DFY006", "error", "workflow.graph", "No start node found.",
                          "Connect a Start node."))
    if ends < 1:
        fs.append(finding("DFY007", "warning", "workflow.graph", "No End/Answer node detected.",
                          "Check the intended workflow termination."))
    for i, edge in enumerate(graph["edges"]):
        if not isinstance(edge, dict):
            fs.append(finding("DFY008", "error", f"edges[{i}]", "Edge is not an object.", "Repair the graph."))
            continue
        if edge.get("source") not in ids or edge.get("target") not in ids:
            fs.append(finding("DFY009", "error", f"edges[{i}]", "Edge references a missing node.",
                              "Reconnect or remove the invalid edge."))
    return fs


# Trigger.dev uses code-defined tasks; regex heuristics are never treated as compiler checks.
TASK_START = re.compile(r"\b(?:task|schemaTask|schedules\.task)\s*\(\s*\{")
TASK_ID = re.compile(r"""\bid\s*:\s*(['"])([A-Za-z][A-Za-z0-9_-]{0,100})\1""")
def audit_trigger(source: str) -> list[Finding]:
    fs = []
    if "@trigger.dev/sdk" not in source and "trigger.dev/sdk" not in source:
        return [finding("TRG001", "warning", "source", "Trigger.dev SDK import not found.",
                        "Supply a Trigger.dev task source file.", "medium")]
    seen: set[str] = set()
    starts = list(TASK_START.finditer(source))
    if not starts:
        return [finding("TRG002", "warning", "source", "No recognizable task({ ... }) declaration found.",
                        "Confirm task definitions manually; this is not a TypeScript parser.", "low")]
    # Limit inspection to the beginning of each task's config.
    for i, match in enumerate(starts):
        preview = source[match.end():min(len(source), match.end()+400)]
        literal = TASK_ID.search(preview)
        loc = f"task[{i}]"
        if not literal:
            fs.append(finding("TRG003", "warning", loc, "Static task ID not found near declaration.",
                              "Check that every exported task has an explicit, unique literal ID.", "low"))
        else:
            ident = literal.group(2)
            if ident in seen:
                fs.append(finding("TRG004", "error", loc, "Duplicate literal task ID detected.",
                                  "Use a unique task ID.", "medium"))
            seen.add(ident)
        if "maxDuration" not in preview:
            fs.append(finding("TRG005", "info", loc, "No task-level maxDuration seen nearby.",
                              "Review project-wide and per-task duration settings; they may be elsewhere.", "low"))
    fs.append(finding("TRG099", "info", "source", "Trigger.dev analysis is source heuristics, not AST/type checking.",
                      "Also run TypeScript checks, Trigger.dev builds and execution tests.", "high"))
    return fs


def audit_activepieces(data: Any) -> list[Finding]:
    if not isinstance(data, dict):
        return [finding("AP001", "error", "root", "Not an Activepieces flow object.",
                        "Provide a flow export or API response.")]
    version = data.get("version", data)
    if not isinstance(version, dict) or not isinstance(version.get("trigger"), dict):
        return [finding("AP002", "error", "root", "Activepieces trigger not found.",
                        "Export a complete flow version.")]
    fs: list[Finding] = []
    visited = 0
    names: set[str] = set()

    def visit(node: Any, loc: str):
        nonlocal visited
        if visited >= 150:
            return
        visited += 1
        if not isinstance(node, dict):
            fs.append(finding("AP003", "error", loc, "Step is not an object.",
                              "Repair or re-export the step."))
            return
        name = node.get("name")
        if isinstance(name, str) and name:
            if name in names:
                fs.append(finding("AP004", "error", loc, "Duplicate step name.",
                                  "Make action names unique."))
            names.add(name)
        else:
            fs.append(finding("AP005", "warning", loc, "Step name missing.",
                              "Give each flow step a stable name."))
        if node.get("valid") is False:
            fs.append(finding("AP006", "warning", loc, "Step marked invalid in exported flow.",
                              "Open and repair the step in Activepieces."))
        next_node = node.get("nextAction")
        if next_node is not None:
            visit(next_node, loc + ".nextAction")
        # Router branches may be shaped differently across versions: recognize common ones.
        for key in ("children", "branches"):
            elements = node.get(key)
            if isinstance(elements, list):
                for index, item in enumerate(elements):
                    if isinstance(item, dict) and isinstance(item.get("action"), dict):
                        visit(item["action"], f"{loc}.{key}[{index}].action")
                    elif isinstance(item, dict) and ("type" in item or "name" in item):
                        visit(item, f"{loc}.{key}[{index}]")
    visit(version["trigger"], "trigger")
    if visited >= 150:
        fs.append(finding("AP007", "warning", "root", "Step scan limit reached.",
                          "Split the flow or audit smaller sections."))
    return fs


def supported_platforms() -> dict:
    return {
        "native_adapters": ["n8n", "dify", "trigger", "activepieces"],
        "formats": {
            "n8n": "workflow JSON",
            "dify": "application DSL YAML or JSON",
            "trigger": "TypeScript/JavaScript task source (heuristic checks only)",
            "activepieces": "flow JSON with version.trigger or trigger"
        },
        "additional_tools": ["audit_openapi", "preflight_url"],
        "other_platforms": "Contribute a format-specific adapter; no universal export format exists.",
    }
