import os
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd

APP_NAME = "MirrorX Backend"
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "mock_data"))

app = Flask(__name__)
CORS(app)

def read_csv_safe(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

# ✅ Clean root route (homepage)
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "message": "👋 Welcome to MirrorX API!",
        "status": "live",
        "routes": ["/status", "/score-history", "/live-score", "/scores", "/run-job"]
    })

# ✅ Health check route
@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "MirrorX backend is live."})

# ✅ Simulated job trigger
@app.route("/run-job", methods=["POST"])
def run_job():
    now = datetime.utcnow().isoformat() + "Z"
    return jsonify({"message": "Scoring job triggered", "timestamp": now}), 200

# ✅ Score history
@app.route("/score-history", methods=["GET"])
def score_history():
    df = read_csv_safe(os.path.join(DATA_DIR, "score_history.csv"))
    return jsonify({"data": df.to_dict(orient="records")}), 200

# ✅ Live score
@app.route("/live-score", methods=["GET"])
def live_score():
    df = read_csv_safe(os.path.join(DATA_DIR, "live_score.csv"))
    return jsonify({"data": df.to_dict(orient="records")}), 200

# ✅ Combined scores endpoint
@app.route("/scores", methods=["GET"])
def scores():
    hist = read_csv_safe(os.path.join(DATA_DIR, "score_history.csv"))
    live = read_csv_safe(os.path.join(DATA_DIR, "live_score.csv"))
    frames = []
    if not hist.empty:
        h = hist.copy()
        h["last_updated"] = h["timestamp"]
        frames.append(h[["user_id", "score_type", "score_value", "last_updated"]])
    if not live.empty:
        l = live.copy()
        l["last_updated"] = l["timestamp"]
        frames.append(l[["user_id", "score_type", "score_value", "last_updated"]])
    if not frames:
        merged = pd.DataFrame(columns=["user_id", "score_type", "score_value", "last_updated"])
    else:
        merged = pd.concat(frames, ignore_index=True)
        merged = merged.sort_values("last_updated").groupby("user_id", as_index=False).tail(1)
    return jsonify({"data": merged.to_dict(orient="records")}), 200

# ✅ Start app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
