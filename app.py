import os
import re
from bson import ObjectId, errors as bson_errors
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv

# Load .env so MONGO_URI, SERPAPI_KEY, etc. are available when running locally
load_dotenv()

# ----- Config -----
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.environ.get("DB_NAME", "jobtracker")
COLL_NAME = os.environ.get("COLL_NAME", "jobs")

# ----- App/DB setup -----
app = Flask(__name__)

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COLL_NAME]
    # quick ping (won't fail Atlas SRV lazily)
    client.admin.command("ping")
except Exception as e:
    # Fail fast with a clear message in logs
    app.logger.error(f"MongoDB connection failed. Check MONGO_URI. Error: {e}")
    raise

# ----- Routes -----
@app.route("/")
def home():
    q = (request.args.get("q") or "").strip()
    source = (request.args.get("source") or "").strip()
    applied = request.args.get("applied")  # "true" | "false" | None

    query = {}
    if q:
        # Case-insensitive search over title/company/location
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"company": {"$regex": q, "$options": "i"}},
            {"location": {"$regex": q, "$options": "i"}},
        ]
    if source:
        query["source"] = source
    if applied in ("true", "false"):
        query["applied"] = (applied == "true")

    # Pull jobs newest-first
    jobs = list(col.find(query).sort([("last_seen", -1), ("first_seen", -1)]))

    # For safety: add a string version of _id for templates/JS
    for j in jobs:
        j["id_str"] = str(j["_id"])

    # Sources list for the filter dropdown
    sources = sorted({doc.get("source", "Unknown") for doc in col.find({}, {"source": 1})})

    return render_template("index.html",
                           jobs=jobs,
                           q=q,
                           source=source,
                           applied=applied,
                           sources=sources)

@app.post("/api/jobs/<job_id>/applied")
def set_applied(job_id: str):
    """
    Accepts either a plain 24-hex ObjectId string ("64e2...") OR
    a string like "ObjectId('64e2...')" from the DOM.
    """
    payload = request.get_json(force=True) or {}
    applied = bool(payload.get("applied", False))

    # Sanitize job_id if it looks like "ObjectId('...')"
    raw = job_id.strip()
    if raw.lower().startswith("objectid("):
        # extract content between single or double quotes
        m = re.search(r"ObjectId\(['\"]?([0-9a-fA-F]{24})['\"]?\)", raw)
        raw = m.group(1) if m else raw

    try:
        _id = ObjectId(raw)
    except bson_errors.InvalidId:
        return jsonify({"ok": False, "error": f"Invalid job_id: {job_id}"}), 400

    res = col.update_one({"_id": _id}, {"$set": {"applied": applied}})
    if res.matched_count == 0:
        return jsonify({"ok": False, "error": "Job not found"}), 404

    return jsonify({"ok": True, "applied": applied})

# ----- Entrypoint -----
if __name__ == "__main__":
    # PORT is set in docker-compose; defaults to 5000 for local python runs
    app.run(port=5003, debug=True)

