"""MCP server exposing HireHunt as agent-friendly tools."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any, TextIO

from hirehunt import __version__
from hirehunt.engine import search_jobs
from hirehunt.query import JobQuery
from hirehunt.registry import default_registry
from hirehunt.validation import benchmark_sources, validate_sources

PROTOCOL_VERSION = "2024-11-05"
DEFAULT_SAVED_SEARCHES = Path.home() / ".hirehunt_saved_searches.json"


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _tool_text(name: str, payload: Any) -> dict[str, Any]:
    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": pretty}],
        "structuredContent": {
            "tool": name,
            "data": payload,
        },
        "isError": False,
    }


def _tool_error(code: str, message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "structuredContent": {
            "error": {
                "code": code,
                "message": message,
            }
        },
        "isError": True,
    }


def _definition_to_dict(definition) -> dict[str, Any]:
    return {
        "name": definition.name,
        "family": definition.family,
        "adapter": definition.adapter,
        "aliases": list(definition.aliases),
        "tags": list(definition.tags),
        "config": dict(definition.config),
        "capabilities": {
            "countries": list(definition.capabilities.countries),
            "job_kinds": [str(item) for item in definition.capabilities.job_kinds],
            "supported_filters": sorted(definition.capabilities.supported_filters),
            "pagination": definition.capabilities.pagination,
            "exhaustive_search": definition.capabilities.exhaustive_search,
            "description": definition.capabilities.description,
        },
    }


class HireHuntMCPServer:
    def __init__(self, saved_searches_file: str | Path | None = None) -> None:
        self.registry = default_registry()
        self.saved_searches_file = Path(saved_searches_file or DEFAULT_SAVED_SEARCHES)

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "serverInfo": {
                        "name": "hirehunt-mcp",
                        "version": __version__,
                    },
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                },
            }

        if method == "notifications/initialized":
            return None

        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": self._tools(),
                },
            }

        if method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {}) or {}
            try:
                result = self._call_tool(name, arguments)
            except Exception as exc:  # pragma: no cover - defensive server path
                result = _tool_error("tool_execution_failed", str(exc))
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }

    def _tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "search_jobs",
                "description": "Search jobs across supported sources. Returns structured jobs, summary, warnings, and source diagnostics.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "sources": {"type": "array", "items": {"type": "string"}},
                        "source_family": {"type": "string"},
                        "city": {"type": "string"},
                        "country": {"type": "string"},
                        "location": {"type": "string"},
                        "company": {"type": "array", "items": {"type": "string"}},
                        "skills": {"type": "array", "items": {"type": "string"}},
                        "exclude": {"type": "array", "items": {"type": "string"}},
                        "job_kind": {"type": "string"},
                        "work_mode": {"type": "string"},
                        "match_mode": {"type": "string", "enum": ["strict", "balanced", "broad"]},
                        "limit": {"type": "integer"},
                        "dedupe_mode": {"type": "string", "enum": ["strict", "heuristic", "fuzzy", "none"]},
                        "dedupe_scope": {"type": "string"},
                        "remote": {"type": "boolean"},
                        "fresher": {"type": "boolean"},
                        "min_exp": {"type": "number"},
                        "max_exp": {"type": "number"},
                        "salary_min": {"type": "number"},
                        "posted_days": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "list_sources",
                "description": "List all concrete registered sources with family and capabilities metadata.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "list_source_families",
                "description": "List all source families and the sources in each family.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_source_definition",
                "description": "Get one source definition including aliases, family, adapter, config, and capabilities.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"source": {"type": "string"}},
                    "required": ["source"],
                },
            },
            {
                "name": "validate_sources",
                "description": "Run live source validation and return parsed counts, sample titles, status, and errors.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "sources": {"type": "array", "items": {"type": "string"}},
                        "source_family": {"type": "string"},
                        "city": {"type": "string"},
                        "country": {"type": "string"},
                        "location": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "benchmark_sources",
                "description": "Benchmark source throughput, requests, parsed counts, and completion state.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "sources": {"type": "array", "items": {"type": "string"}},
                        "source_family": {"type": "string"},
                        "city": {"type": "string"},
                        "country": {"type": "string"},
                        "location": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "save_search",
                "description": "Persist a named search for later use by agents or automation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "query": {"type": "string"},
                        "sources": {"type": "array", "items": {"type": "string"}},
                        "source_family": {"type": "string"},
                        "city": {"type": "string"},
                        "country": {"type": "string"},
                        "location": {"type": "string"},
                        "company": {"type": "array", "items": {"type": "string"}},
                        "skills": {"type": "array", "items": {"type": "string"}},
                        "exclude": {"type": "array", "items": {"type": "string"}},
                        "job_kind": {"type": "string"},
                        "work_mode": {"type": "string"},
                        "match_mode": {"type": "string"},
                        "limit": {"type": "integer"},
                        "dedupe_mode": {"type": "string"},
                        "dedupe_scope": {"type": "string"},
                        "remote": {"type": "boolean"},
                        "fresher": {"type": "boolean"},
                        "min_exp": {"type": "number"},
                        "max_exp": {"type": "number"},
                        "salary_min": {"type": "number"},
                        "posted_days": {"type": "integer"},
                    },
                    "required": ["name", "query"],
                },
            },
            {
                "name": "list_saved_searches",
                "description": "List all saved searches.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_saved_search",
                "description": "Get one saved search by name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
            {
                "name": "run_saved_search",
                "description": "Execute a saved search and return the same structured results as search_jobs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        ]

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "search_jobs":
            result = search_jobs(**self._search_kwargs(arguments))
            return _tool_text(name, result.to_json_envelope(query=self._query_echo(arguments), full=False))
        if name == "list_sources":
            payload = [_definition_to_dict(self.registry.definition(source)) for source in self.registry.names()]
            return _tool_text(name, payload)
        if name == "list_source_families":
            payload = {
                family: self.registry.family_sources(family)
                for family in self.registry.families()
            }
            return _tool_text(name, payload)
        if name == "get_source_definition":
            source = arguments.get("source", "")
            if not source:
                return _tool_error("missing_source", "source is required")
            return _tool_text(name, _definition_to_dict(self.registry.definition(source)))
        if name == "validate_sources":
            query = JobQuery.from_kwargs(**self._search_kwargs(arguments))
            sources = arguments.get("sources")
            results = [asdict(item) | {"ok": item.ok} for item in validate_sources(query, sources)]
            return _tool_text(name, results)
        if name == "benchmark_sources":
            query = JobQuery.from_kwargs(**self._search_kwargs(arguments))
            sources = arguments.get("sources")
            results = [
                asdict(item) | {"jobs_per_second": item.jobs_per_second}
                for item in benchmark_sources(query, sources)
            ]
            return _tool_text(name, results)
        if name == "save_search":
            saved = self._load_saved_searches()
            payload = self._saved_search_payload(arguments)
            saved[payload["name"]] = payload
            self._write_saved_searches(saved)
            return _tool_text(name, payload)
        if name == "list_saved_searches":
            return _tool_text(name, self._load_saved_searches())
        if name == "get_saved_search":
            name_arg = arguments.get("name", "")
            saved = self._load_saved_searches().get(name_arg)
            if saved is None:
                return _tool_error("saved_search_not_found", f"saved search '{name_arg}' not found")
            return _tool_text(name, saved)
        if name == "run_saved_search":
            name_arg = arguments.get("name", "")
            saved = self._load_saved_searches().get(name_arg)
            if saved is None:
                return _tool_error("saved_search_not_found", f"saved search '{name_arg}' not found")
            result = search_jobs(**self._saved_to_search_kwargs(saved))
            return _tool_text(name, result.to_json_envelope(query=saved, full=False))
        return _tool_error("unknown_tool", f"Unknown tool: {name}")

    def _search_kwargs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "search_term": arguments.get("query", ""),
            "sources": arguments.get("sources") or "auto",
            "source_family": arguments.get("source_family", ""),
            "city": arguments.get("city", ""),
            "country": arguments.get("country", ""),
            "location": arguments.get("location", ""),
            "companies": arguments.get("company", []),
            "skills": arguments.get("skills", []),
            "exclude": arguments.get("exclude", []),
            "job_kind": arguments.get("job_kind") or None,
            "work_mode": arguments.get("work_mode") or None,
            "remote": arguments.get("remote"),
            "fresher": arguments.get("fresher"),
            "experience_min": arguments.get("min_exp"),
            "experience_max": arguments.get("max_exp"),
            "salary_min": arguments.get("salary_min"),
            "posted_within_days": arguments.get("posted_days"),
            "results_wanted": arguments.get("limit", 20),
            "dedupe_mode": arguments.get("dedupe_mode", "strict"),
            "dedupe_scope": arguments.get("dedupe_scope", "title-company-location-country"),
            "match_mode": arguments.get("match_mode", "balanced"),
        }

    def _query_echo(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "query": arguments.get("query", ""),
            "sources": arguments.get("sources") or "auto",
            "source_family": arguments.get("source_family", ""),
            "city": arguments.get("city", ""),
            "country": arguments.get("country", ""),
            "location": arguments.get("location", ""),
            "company": arguments.get("company", []),
            "skills": arguments.get("skills", []),
            "exclude": arguments.get("exclude", []),
            "job_kind": arguments.get("job_kind"),
            "work_mode": arguments.get("work_mode"),
            "match_mode": arguments.get("match_mode", "balanced"),
            "limit": arguments.get("limit", 20),
            "dedupe_mode": arguments.get("dedupe_mode", "strict"),
            "dedupe_scope": arguments.get("dedupe_scope", "title-company-location-country"),
            "remote": arguments.get("remote"),
            "fresher": arguments.get("fresher"),
            "min_exp": arguments.get("min_exp"),
            "max_exp": arguments.get("max_exp"),
            "salary_min": arguments.get("salary_min"),
            "posted_days": arguments.get("posted_days"),
        }

    def _saved_search_payload(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = self._query_echo(arguments)
        payload["name"] = arguments["name"]
        return payload

    def _saved_to_search_kwargs(self, saved: dict[str, Any]) -> dict[str, Any]:
        return self._search_kwargs(
            {
                "query": saved.get("query", ""),
                "sources": saved.get("sources") or "auto",
                "source_family": saved.get("source_family", ""),
                "city": saved.get("city", ""),
                "country": saved.get("country", ""),
                "location": saved.get("location", ""),
                "company": saved.get("company", []),
                "skills": saved.get("skills", []),
                "exclude": saved.get("exclude", []),
                "job_kind": saved.get("job_kind"),
                "work_mode": saved.get("work_mode"),
                "match_mode": saved.get("match_mode", "balanced"),
                "limit": saved.get("limit", 20),
                "dedupe_mode": saved.get("dedupe_mode", "strict"),
                "dedupe_scope": saved.get("dedupe_scope", "title-company-location-country"),
                "remote": saved.get("remote"),
                "fresher": saved.get("fresher"),
                "min_exp": saved.get("min_exp"),
                "max_exp": saved.get("max_exp"),
                "salary_min": saved.get("salary_min"),
                "posted_days": saved.get("posted_days"),
            }
        )

    def _load_saved_searches(self) -> dict[str, dict[str, Any]]:
        if not self.saved_searches_file.exists():
            return {}
        return json.loads(self.saved_searches_file.read_text(encoding="utf-8"))

    def _write_saved_searches(self, searches: dict[str, dict[str, Any]]) -> None:
        self.saved_searches_file.parent.mkdir(parents=True, exist_ok=True)
        self.saved_searches_file.write_text(json.dumps(searches, ensure_ascii=False, indent=2), encoding="utf-8")


def serve(server: HireHuntMCPServer | None = None, *, stdin=None, stdout=None) -> int:
    server = server or HireHuntMCPServer()
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    while True:
        request = _read_message(stdin)
        if request is None:
            break
        if isinstance(request, dict) and "_parse_error" in request:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": request["_parse_error"]},
            }
        else:
            response = server.handle(request)
            if response is None:
                continue
        _write_message(stdout, response)
    return 0


def _read_message(stream: TextIO) -> dict[str, Any] | None:
    first_line = stream.readline()
    if not first_line:
        return None
    if first_line.lower().startswith("content-length:"):
        try:
            content_length = int(first_line.split(":", 1)[1].strip())
        except ValueError:
            return {"_parse_error": "Invalid Content-Length header"}
        while True:
            header_line = stream.readline()
            if not header_line:
                return None
            if header_line in {"\n", "\r\n", ""}:
                break
        payload = stream.read(content_length)
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {"_parse_error": "Parse error"}
    line = first_line.strip()
    if not line:
        return _read_message(stream)
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"_parse_error": "Parse error"}


def _write_message(stream: TextIO, payload: dict[str, Any]) -> None:
    body = _json_dumps(payload)
    stream.write(f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}")
    stream.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hirehunt-mcp", description="Run the HireHunt MCP server over stdio.")
    parser.add_argument(
        "--saved-searches-file",
        default=str(DEFAULT_SAVED_SEARCHES),
        help="Path to the saved-searches JSON registry used by MCP tools.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return serve(HireHuntMCPServer(saved_searches_file=args.saved_searches_file))


if __name__ == "__main__":
    raise SystemExit(main())
