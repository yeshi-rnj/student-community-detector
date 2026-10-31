"""Flask app: REST API + single-page UI for the Student Community Detector."""
import csv
import io
import math
import hmac
import os
import threading
from urllib.parse import urlparse

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from data import DEFAULT_THRESHOLD, generate_students
from graph_engine import Student, StudentGraph

app = Flask(__name__)
if os.environ.get("TRUST_PROXY") == "1":  # running behind nginx / a platform load balancer
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # reject oversized uploads

STATE = {"students": generate_students(), "version": 0}
LOCK = threading.RLock()
MAX_IMPORT_ROWS = 2000
MAX_STUDENTS = 2000
_GRAPH_CACHE = {}


def set_students(students):
    """Replace the dataset (call with LOCK held)."""
    STATE["students"] = students
    STATE["version"] += 1
    _GRAPH_CACHE.clear()


# --------------------------------------------------------------- security
@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.before_request
def require_password():
    """Optional HTTP Basic auth: set APP_PASSWORD (and optionally APP_USER) to enable."""
    password = os.environ.get("APP_PASSWORD")
    if not password or request.path == "/healthz":
        return None
    auth = request.authorization
    user = os.environ.get("APP_USER", "admin")
    if (auth and auth.type == "basic"
            and hmac.compare_digest((auth.username or "").encode(), user.encode())
            and hmac.compare_digest((auth.password or "").encode(), password.encode())):
        return None
    return Response("Login required.", 401, {"WWW-Authenticate": 'Basic realm="Student Community Detector"'})


@app.before_request
def reject_cross_site_writes():
    """CSRF guard: browsers always send Origin on cross-site POST/DELETE."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("Origin")
        if origin and urlparse(origin).netloc != request.host:
            return error("Cross-site requests are not allowed.", 403)


@app.after_request
def add_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
        "base-uri 'self'; object-src 'none'; form-action 'self'",
    )
    return resp


# ---------------------------------------------------------------- helpers
def csv_safe(value) -> str:
    """Neutralise spreadsheet formulas (CSV injection) in exported cells."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def error(message, status=400):
    return jsonify({"error": message}), status


def read_threshold() -> float:
    try:
        value = float(request.args.get("threshold", DEFAULT_THRESHOLD))
    except ValueError:
        value = DEFAULT_THRESHOLD
    if not math.isfinite(value):  # "nan" would otherwise produce an edgeless graph
        value = DEFAULT_THRESHOLD
    return min(max(value, 0.05), 1.0)


def read_method() -> str:
    return "dfs" if request.args.get("method", "bfs").lower() == "dfs" else "bfs"


def build_graph() -> StudentGraph:
    """Build (or reuse) the graph for the current dataset and threshold."""
    threshold = read_threshold()
    with LOCK:
        key = (STATE["version"], threshold)
        graph = _GRAPH_CACHE.get(key)
        if graph is None:
            if len(_GRAPH_CACHE) >= 8:
                _GRAPH_CACHE.clear()
            graph = _GRAPH_CACHE[key] = StudentGraph(list(STATE["students"]), threshold)
        return graph


def clean_interests(raw) -> frozenset:
    if raw is None:
        return frozenset()
    if isinstance(raw, str):
        raw = raw.replace(";", ",").split(",")
    elif not isinstance(raw, (list, tuple, set, frozenset)):
        return frozenset()
    cleaned = {str(i).strip().lower() for i in raw if str(i).strip()}
    return frozenset(i[:40] for i in cleaned)


def next_id() -> int:
    return max((s.id for s in STATE["students"]), default=0) + 1


def parse_student(data, sid: int):
    if not isinstance(data, dict):
        return None, "Send the student as a JSON object."
    name = str(data.get("name") or "").strip()
    if not name:
        return None, "Enter the student's name."
    if len(name) > 60:
        return None, "Names can be at most 60 characters."
    interests = clean_interests(data.get("interests", []))
    if not interests:
        return None, "Add at least one interest."
    if len(interests) > 12:
        return None, "Add at most 12 interests."
    try:
        year = int(data.get("year") or 1)
    except (TypeError, ValueError):
        return None, "Year must be a number from 1 to 6."
    if not 1 <= year <= 6:
        return None, "Year must be a number from 1 to 6."
    department = str(data.get("department") or "").strip()[:40] or "Undeclared"
    return Student(sid, name, department, year, interests), None


# ----------------------------------------------------------------- pages
@app.get("/")
def index():
    return render_template("index.html", default_threshold=DEFAULT_THRESHOLD)


# ------------------------------------------------------------------- API
@app.get("/api/graph")
def api_graph():
    return jsonify(build_graph().analyze(read_method()))


@app.get("/api/traverse")
def api_traverse():
    graph = build_graph()
    try:
        start = int(request.args["start"])
    except (KeyError, ValueError):
        return error("Choose a student to start from.")
    if start not in graph.students:
        return error("That student does not exist.", 404)
    algo = "dfs" if request.args.get("algo", "bfs").lower() == "dfs" else "bfs"
    result = graph.traverse(start, algo)
    return jsonify({
        "algo": algo,
        "start": start,
        "steps": result["steps"],
        "reached": len(result["order"]),
        "max_level": max(result["level"].values()),
    })


@app.get("/api/path")
def api_path():
    graph = build_graph()
    try:
        src, dst = int(request.args["src"]), int(request.args["dst"])
    except (KeyError, ValueError):
        return error("Choose two students.")
    if src not in graph.students or dst not in graph.students:
        return error("That student does not exist.", 404)
    path = graph.shortest_path(src, dst)
    if path is None:
        return jsonify({"path": None, "hops": None})
    weights = [round(graph.adj[a][b], 3) for a, b in zip(path, path[1:])]
    return jsonify({"path": path, "hops": len(path) - 1, "weights": weights})


@app.get("/api/recommend/<int:sid>")
def api_recommend(sid):
    graph = build_graph()
    if sid not in graph.students:
        return error("That student does not exist.", 404)
    return jsonify({"student": sid, "recommendations": graph.recommend(sid)})


@app.get("/api/interests")
def api_interests():
    counts = {}
    for s in list(STATE["students"]):
        for i in s.interests:
            counts[i] = counts.get(i, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return jsonify([{"name": k, "count": v} for k, v in ranked])


@app.post("/api/students")
def api_add_student():
    payload = request.get_json(silent=True)
    with LOCK:
        if len(STATE["students"]) >= MAX_STUDENTS:
            return error(f"The dataset is limited to {MAX_STUDENTS} students.", 409)
        student, problem = parse_student(payload, next_id())
        if problem:
            return error(problem)
        set_students(STATE["students"] + [student])
    return jsonify(student.to_dict()), 201


@app.delete("/api/students/<int:sid>")
def api_delete_student(sid):
    with LOCK:
        remaining = [s for s in STATE["students"] if s.id != sid]
        if len(remaining) == len(STATE["students"]):
            return error("That student does not exist.", 404)
        set_students(remaining)
    return jsonify({"deleted": sid})


@app.post("/api/reset")
def api_reset():
    with LOCK:
        set_students(generate_students())
        return jsonify({"students": len(STATE["students"])})


@app.get("/api/export.csv")
def api_export():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["name", "department", "year", "interests"])
    for s in list(STATE["students"]):
        writer.writerow([csv_safe(s.name), csv_safe(s.department), s.year,
                         csv_safe(";".join(sorted(s.interests)))])
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"},
    )


@app.post("/api/import")
def api_import():
    """Replace the dataset with a CSV (columns: name, department, year, interests;
    interests separated by semicolons)."""
    upload = request.files.get("file")
    text = upload.read().decode("utf-8-sig", errors="replace") if upload else request.get_data(as_text=True)
    if not text.strip():
        return error("Choose a CSV file with the columns name, department, year, interests.")
    reader = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower() for f in (reader.fieldnames or [])}
    if not {"name", "interests"} <= fields:
        return error("The CSV needs at least the columns name and interests.")

    students, skipped = [], 0
    for row in reader:
        if len(students) >= MAX_IMPORT_ROWS:
            break
        row = {(k or "").strip().lower(): v for k, v in row.items()}
        student, problem = parse_student(row, len(students) + 1)
        if problem:
            skipped += 1
        else:
            students.append(student)
    if not students:
        return error("No valid rows found. Each row needs a name and at least one interest.")
    with LOCK:
        set_students(students)
    return jsonify({"imported": len(students), "skipped": skipped})


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
