import io
import json
import tempfile
import unittest
from unittest.mock import patch

from hirehunt.mcp_server import HireHuntMCPServer, serve
from hirehunt.models import Job


def _fake_result():
    return type(
        "Result",
        (),
        {
            "jobs": [Job("Python Developer", "UST", "naukri", "https://example.com/job", city="Bengaluru")],
            "errors": {},
            "warnings": [],
            "partial": False,
            "selected_sources": ["naukri"],
            "schema_version": "1.0",
            "stats": {},
            "to_json_envelope": lambda self, query=None, full=False: {
                "ok": True,
                "status": "ok",
                "meta": {"format": "json-full" if full else "json", "schema_version": "1.0"},
                "query": query,
                "summary": {"job_count": 1},
                "jobs": [job.to_compact_dict() for job in self.jobs],
            },
        },
    )()


class MCPServerTests(unittest.TestCase):
    def test_initialize(self):
        server = HireHuntMCPServer()
        response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["result"]["serverInfo"]["name"], "hirehunt-mcp")
        self.assertEqual(response["result"]["protocolVersion"], "2024-11-05")

    def test_tools_list(self):
        server = HireHuntMCPServer()
        response = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tool_names = {item["name"] for item in response["result"]["tools"]}
        self.assertIn("search_jobs", tool_names)
        self.assertIn("validate_sources", tool_names)
        self.assertIn("run_saved_search", tool_names)

    def test_search_tool_returns_structured_content(self):
        server = HireHuntMCPServer()
        with patch("hirehunt.mcp_server.search_jobs", return_value=_fake_result()):
            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "search_jobs",
                        "arguments": {"query": "python developer", "sources": ["naukri"], "limit": 1},
                    },
                }
            )
        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["tool"], "search_jobs")
        self.assertEqual(result["structuredContent"]["data"]["summary"]["job_count"], 1)

    def test_saved_search_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = HireHuntMCPServer(saved_searches_file=f"{tmp}/saved.json")
            add_response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "save_search",
                        "arguments": {"name": "py-blr", "query": "python developer", "city": "Bengaluru"},
                    },
                }
            )
            self.assertFalse(add_response["result"]["isError"])

            get_response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {"name": "get_saved_search", "arguments": {"name": "py-blr"}},
                }
            )
            self.assertEqual(get_response["result"]["structuredContent"]["data"]["query"], "python developer")

    def test_serve_stdio_loop(self):
        body = json.dumps({"jsonrpc": "2.0", "id": 6, "method": "ping", "params": {}})
        stdin = io.StringIO(f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}")
        stdout = io.StringIO()
        code = serve(HireHuntMCPServer(), stdin=stdin, stdout=stdout)
        raw = stdout.getvalue()
        self.assertTrue(raw.startswith("Content-Length: "))
        payload = json.loads(raw.split("\r\n\r\n", 1)[1])
        self.assertEqual(code, 0)
        self.assertEqual(payload["id"], 6)
        self.assertEqual(payload["result"], {})

    def test_serve_ndjson_fallback(self):
        stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping", "params": {}}) + "\n")
        stdout = io.StringIO()
        code = serve(HireHuntMCPServer(), stdin=stdin, stdout=stdout)
        payload = json.loads(stdout.getvalue().split("\r\n\r\n", 1)[1])
        self.assertEqual(code, 0)
        self.assertEqual(payload["id"], 7)


if __name__ == "__main__":
    unittest.main()
