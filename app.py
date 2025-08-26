import os
import re
from bson import ObjectId, errors as bson_errors
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

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
    status = (request.args.get("status") or "").strip()

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
    if status:
        query["status"] = status

    # Pull jobs newest-first
    jobs = list(col.find(query).sort([("last_seen", -1), ("first_seen", -1)]))

    # For safety: add a string version of _id for templates/JS
    for j in jobs:
        j["id_str"] = str(j["_id"])

    # Sources list for the filter dropdown
    sources = sorted({doc.get("source", "Unknown").title() for doc in col.find({}, {"source": 1})})

    # Status list for the filter dropdown
    statuses = sorted({doc.get("status", "Unknown") for doc in col.find({}, {"status": 1})})

    return render_template("index.html",
                           jobs=jobs,
                           q=q,
                           source=source,
                           applied=applied,
                           status=status,
                           sources=sources,
                           statuses=statuses)

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

@app.post("/api/jobs/<job_id>/status")
def set_status(job_id: str):
    payload = request.get_json(force=True) or {}
    status = payload.get("status", "")

    try:
        _id = ObjectId(job_id)
    except bson_errors.InvalidId:
        return jsonify({"ok": False, "error": f"Invalid job_id: {job_id}"}), 400

    res = col.update_one({"_id": _id}, {"$set": {"status": status}})
    if res.matched_count == 0:
        return jsonify({"ok": False, "error": "Job not found"}), 404

    return jsonify({"ok": True, "status": status})

@app.post("/add_job")
def add_job():
    data = request.get_json()
    title = data.get("title")
    company = data.get("company")
    location = data.get("location")
    applied_date = data.get("applied_date")
    status = data.get("status")

    if not title or not company:
        return jsonify({"ok": False, "error": "Title and company are required"}), 400

    job_data = {
        "title": title,
        "company": company,
        "location": location,
        "source": "Manual",
        "first_seen": datetime.now(timezone.utc).date().isoformat(),
        "last_seen": datetime.now(timezone.utc).date().isoformat(),
        "applied": True,
        "added_manually_date": applied_date or datetime.now(timezone.utc).date().isoformat(),
        "status": status or "Applied"
    }

    try:
        res = col.insert_one(job_data)
        return jsonify({"ok": True, "id": str(res.inserted_id)}), 201
    except Exception as e:
        app.logger.error(f"Failed to insert manual job: {e}")
        return jsonify({"ok": False, "error": f"Database error: {e}"}), 500

@app.route("/api/jobs/<job_id>/delete", methods=["DELETE"])
def delete_job(job_id: str):
    try:
        _id = ObjectId(job_id)
    except bson_errors.InvalidId:
        return jsonify({"ok": False, "error": f"Invalid job_id: {job_id}"}), 400

    # Ensure only manually added jobs can be deleted
    job = col.find_one({"_id": _id})
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    if job.get("source") != "Manual":
        return jsonify({"ok": False, "error": "Only manually added jobs can be deleted"}), 403

    res = col.delete_one({"_id": _id})
    if res.deleted_count == 0:
        return jsonify({"ok": False, "error": "Job not found"}), 404

    return jsonify({"ok": True}), 200

# ----- Entrypoint -----
if __name__ == "__main__":
    # PORT is set in docker-compose; defaults to 5000 for local python runs
    app.run(port=5003, debug=True)