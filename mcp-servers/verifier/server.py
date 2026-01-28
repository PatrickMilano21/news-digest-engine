"""
MCP v0: Verifier Server
3 tools: run_tests, get_run, ui_smoke
"""
import sys
import json
import subprocess
import urllib.request
import urllib.error
import re

# === Config ===
BASE_URL = "http://localhost:8001"

# === Tool Definitions ===
TOOLS = [
    {
        "name": "run_tests",
        "description": "Run the test suite (make test)",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_run",
        "description": "Fetch run details from /debug/run/{run_id}",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "The run ID to fetch"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "ui_smoke",
        "description": "Smoke test UI: visit /ui/date/{date}, click first item, verify back-link",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "audit_error_handlers",
        "description": "Audit src/main.py for ProblemDetails consistency: finds all HTTPException raises, exception handlers, and JSONResponse usages",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# === JSON-RPC Helpers ===
def respond(req_id, result):
    """Send a successful JSON-RPC response."""
    msg = {"jsonrpc": "2.0", "id": req_id, "result": result}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def respond_error(req_id, code, message):
    """Send a JSON-RPC error response."""
    msg = {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


# === Tool Implementations (stubs for now) ===
def handle_run_tests(params):
    """Run make test and return structured result."""
    try:
        result = subprocess.run(
            ["make", "test"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=r"C:\Users\pmilano\Desktop\dev\news-digest-engine",
        )
        
        # Truncate output to last 6000 chars
        stdout_tail = result.stdout[-6000:] if result.stdout else ""
        stderr_tail = result.stderr[-6000:] if result.stderr else ""

        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": -1, "error": "timeout after 120s"}
    except Exception as e:
        return {"ok": False, "exit_code": -1, "error": str(e)}


def handle_get_run(params):
    """Fetch run details from /debug/run/{run_id}."""
    run_id = params.get("run_id", "")
    if not run_id:
        return {"ok": False, "error": "run_id is required"}

    url = f"{BASE_URL}/debug/run/{run_id}"

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            return {
                "ok": True,
                "status_code": resp.status,
                "run": data,
            }
    except urllib.error.HTTPError as e:
        body_snippet = e.read().decode("utf-8")[:500] if e.fp else ""
        return {
            "ok": False,
            "status_code": e.code,
            "run": None,
            "body_snippet": body_snippet,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def handle_ui_smoke(params):
    """Smoke test UI navigation: date page -> item page -> back link."""
    date = params.get("date", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {"ok": False, "error": "date must be YYYY-MM-DD format"}

    base_url = BASE_URL
    date_url = f"{base_url}/ui/date/{date}"
    
    checks = {
        "date_page_200": False,
        "found_item_link": False,
        "item_page_200": False,
        "found_back_link": False,
    }
    item_url = None
    debug = {}

    try:
        # Step 1: Fetch date page
        req = urllib.request.Request(date_url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                checks["date_page_200"] = True
            date_html = resp.read().decode("utf-8")

        # Step 2: Find first item link
        match = re.search(r'href="(/ui/item/(\d+))"', date_html)
        if match:
            checks["found_item_link"] = True
            item_path = match.group(1)
            item_url = f"{base_url}{item_path}"
        else:
            debug["body_snippet"] = date_html[:500]
            return {"ok": False, "date_url": date_url, "item_url": None, "checks": checks, "debug": debug} 

        # Step 3: Fetch item page
        req = urllib.request.Request(item_url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                checks["item_page_200"] = True
            item_html = resp.read().decode("utf-8")

        # Step 4: Check for back-link to date page
        if f"/ui/date/{date}" in item_html:
            checks["found_back_link"] = True

        all_passed = all(checks.values())
        return {
            "ok": all_passed,
            "date_url": date_url,
            "item_url": item_url,
            "checks": checks,
        }

    except urllib.error.HTTPError as e:
        debug["http_error"] = {"url": e.url, "code": e.code}
        return {"ok": False, "date_url": date_url, "item_url": item_url, "checks": checks, "debug": debug} 
    except Exception as e:
        debug["error"] = str(e)
        return {"ok": False, "date_url": date_url, "item_url": item_url, "checks": checks, "debug": debug} 



def handle_audit_error_handlers(params):
    """Audit src/main.py for ProblemDetails consistency."""
    main_py_path = r"C:\Users\pmilano\Desktop\dev\news-digest-engine\src\main.py"

    try:
        with open(main_py_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")
    except Exception as e:
        return {"ok": False, "error": f"Could not read {main_py_path}: {e}"}

    # Find all raise HTTPException
    http_exceptions = []
    for i, line in enumerate(lines, 1):
        if "raise HTTPException" in line:
            # Extract status code and detail
            match = re.search(r'status_code=(\d+).*detail="([^"]*)"', line)
            if match:
                http_exceptions.append({
                    "line": i,
                    "status": int(match.group(1)),
                    "detail": match.group(2),
                })
            else:
                http_exceptions.append({"line": i, "raw": line.strip()})

    # Find exception handlers
    exception_handlers = []
    for i, line in enumerate(lines, 1):
        if "@app.exception_handler" in line:
            # Get the exception type from the decorator
            match = re.search(r'@app\.exception_handler\((\w+)\)', line)
            exc_type = match.group(1) if match else "unknown"
            exception_handlers.append({"line": i, "exception_type": exc_type})

    # Find JSONResponse usages
    json_responses = []
    for i, line in enumerate(lines, 1):
        if "JSONResponse(" in line:
            # Extract status code if present
            match = re.search(r'status_code=(\d+)', line)
            status = int(match.group(1)) if match else None
            json_responses.append({"line": i, "status_code": status})

    # Check for issues
    issues = []

    # Issue: JSONResponse with 4xx/5xx not in exception handler context
    # (simplified check: just flag any 4xx/5xx JSONResponse for review)
    for jr in json_responses:
        if jr["status_code"] and jr["status_code"] >= 400:
            # Check if it's in a handler (within 50 lines after @app.exception_handler)
            # Using "after" because handler functions follow their decorators
            is_in_handler = any(
                0 < (jr["line"] - eh["line"]) < 50
                for eh in exception_handlers
            )
            if not is_in_handler:
                issues.append({
                    "type": "error_response_outside_handler",
                    "line": jr["line"],
                    "status_code": jr["status_code"],
                })

    # Check for expected handlers
    expected_handlers = {"HTTPException", "Exception", "RequestValidationError"}
    found_handlers = {eh["exception_type"] for eh in exception_handlers}
    missing_handlers = expected_handlers - found_handlers
    if missing_handlers:
        issues.append({
            "type": "missing_handler",
            "missing": list(missing_handlers),
        })

    return {
        "ok": len(issues) == 0,
        "http_exceptions": http_exceptions,
        "exception_handlers": exception_handlers,
        "json_responses": json_responses,
        "issues": issues,
        "summary": {
            "total_http_exceptions": len(http_exceptions),
            "total_exception_handlers": len(exception_handlers),
            "total_json_responses": len(json_responses),
            "total_issues": len(issues),
        },
    }


TOOL_HANDLERS = {
    "run_tests": handle_run_tests,
    "get_run": handle_get_run,
    "ui_smoke": handle_ui_smoke,
    "audit_error_handlers": handle_audit_error_handlers,
}


# === Main Loop ===
def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        # MCP Protocol Methods
        if method == "initialize":
            respond(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "verifier", "version": "0.1.0"},
            })

        elif method == "notifications/initialized":
            # No response needed for notifications
            pass

        elif method == "tools/list":
            respond(req_id, {"tools": TOOLS})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})

            if tool_name not in TOOL_HANDLERS:
                respond_error(req_id, -32602, f"Unknown tool: {tool_name}")
            else:
                result = TOOL_HANDLERS[tool_name](tool_args)
                respond(req_id, {
                    "content": [{"type": "text", "text": json.dumps(result)}]
                })

        else:
            respond_error(req_id, -32601, f"Unknown method: {method}")


if __name__ == "__main__":
    main()
