"""Source-backed OpenAPI checks and URL preflight, neither invokes remote services."""
from __future__ import annotations

import json
from collections import Counter

from .core import _check, _strict_json, finding, _summary


def audit_openapi(spec_json: str) -> dict:
    """Delegate OpenAPI checks to Ahmad Yar GPT Tools, strip unsafe input strings."""
    source = _check(spec_json)
    try:
        spec = _strict_json(source)
    except (ValueError, TypeError, RecursionError):
        return _summary("openapi", [finding(
            "API001", "error", "input", "Invalid OpenAPI JSON.",
            "Supply a valid OpenAPI 3.x JSON document."
        )])
    if not isinstance(spec, dict):
        return _summary("openapi", [finding(
            "API002", "error", "input", "OpenAPI root must be an object.",
            "Supply a valid JSON object."
        )])
    from gpt_tools.openapi_action_auditor import audit
    raw = audit(spec)
    # Underlying messages/locations sometimes contain user-controlled operation IDs
    # or path segments. Expose stable, useful categories without echoing those values.
    def describe(message: str) -> tuple[str, str, str]:
        categories = (
            ("Duplicate operationId", "API_DUPLICATE_ID", "Duplicate operationId in OpenAPI actions.",
             "Give each operation a unique operationId."),
            ("Missing operationId", "API_MISSING_ID", "OpenAPI operation has no operationId.",
             "Set a stable, unique operationId."),
            ("HTTPS", "API_HTTPS", "An OpenAPI server is not configured for HTTPS.",
             "Use public HTTPS endpoints."),
            ("Localhost", "API_LOCALHOST", "A server points to localhost.",
             "Use a deployable public endpoint, if appropriate."),
            ("Missing info", "API_MISSING_INFO", "OpenAPI info metadata is missing.",
             "Add an info object with title and version."),
            ("No API paths", "API_NO_PATHS", "OpenAPI declares no paths.",
             "Define the API paths and operations."),
            ("response", "API_RESPONSES", "An operation may have missing or incomplete responses.",
             "Define correct success and error responses."),
            ("security", "API_SECURITY", "An operation may lack security requirements.",
             "Declare the intended authentication requirements."),
            ("summary", "API_SUMMARY", "Operation documentation may be incomplete.",
             "Add a clear summary or description."),
            ("parameter", "API_PARAMETER", "An operation parameter may be incomplete.",
             "Include parameter names, descriptions, and schemas."),
        )
        for pattern, code, title, fix in categories:
            if pattern.lower() in message.lower():
                return code, title, fix
        return ("API_OTHER", "OpenAPI usability finding detected.",
                "Review the OpenAPI 3.x schema and tool integration settings.")

    counter = Counter(r.level for r in raw)
    results = []
    for i, item in enumerate(raw[:100]):
        code, title, fix = describe(item.message)
        results.append({
            "rule": code,
            "severity": item.level,
            "location": f"finding[{i}]",
            "message": title,
            "recommendation": fix,
            "confidence": "medium",
        })
    return {
        "platform": "openapi",
        "supported": True,
        "status": "findings" if raw else "no_findings_detected",
        "summary": {"errors": counter["error"], "warnings": counter["warning"],
                    "total": len(raw)},
        "findings": results,
        "truncated_findings": max(0, len(raw)-100),
        "disclaimer": "Best-effort static checks. Full OpenAPI validation requires a dedicated schema validator.",
    }



def preflight_url(url: str) -> dict:
    source = _check(url)
    if len(source) > 2048:
        raise ValueError("URL exceeds 2048 characters")
    from gpt_tools.url_safety_guard import evaluate_url
    # Deliberately no DNS access, no redirect following and no fetch.
    decision = evaluate_url(source, allow_http=False, resolve_dns=False)
    # Return no raw or normalized URL: query strings can contain credentials.
    return {
        "decision": "block" if not decision.allowed else "manual_review",
        "reason": decision.reason,
        "url_included": False,
        "network_requests": 0,
        "disclaimer": (
            "Passing syntax/IP checks never makes a URL safe. DNS, redirects, "
            "TOCTOU, redirects to private networks and request-time controls must be checked by the fetcher."
        ),
    }
