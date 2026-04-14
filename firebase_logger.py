"""
Firebase Logger
Writes trade logs and balance snapshots to Firestore.
Uses REST API — no SDK needed.
"""

import os, json, time, requests
from datetime import datetime, timezone


FIREBASE_URL = os.environ.get("FIREBASE_URL", "")
# e.g. https://YOUR_PROJECT_ID-default-rtdb.firebaseio.com
# OR set FIREBASE_URL to your Firestore REST base URL


class FirebaseLogger:
    def __init__(self):
        self.base = FIREBASE_URL.rstrip("/")
        self.enabled = bool(self.base)
        if not self.enabled:
            print("⚠ FIREBASE_URL not set — logging to console only")

    def log_trade(self, data: dict):
        if not self.enabled:
            print(f"[TRADE LOG] {json.dumps(data, indent=2)}")
            return
        try:
            ts  = int(time.time() * 1000)
            url = f"{self.base}/trades/{ts}.json"
            r   = requests.put(url, json=data, timeout=5)
            if r.status_code == 200:
                print(f"✅ Trade logged to Firebase")
            else:
                print(f"⚠ Firebase error {r.status_code}: {r.text}")
        except Exception as e:
            print(f"⚠ Firebase log failed: {e}")

    def log_snapshot(self, data: dict):
        if not self.enabled:
            print(f"[SNAPSHOT] {json.dumps(data)}")
            return
        try:
            ts  = int(time.time() * 1000)
            url = f"{self.base}/snapshots/{ts}.json"
            requests.put(url, json=data, timeout=5)
        except Exception as e:
            print(f"⚠ Snapshot log failed: {e}")

    def get_trades(self, limit=50) -> list:
        if not self.enabled:
            return []
        try:
            url = f"{self.base}/trades.json?orderBy=%22$key%22&limitToLast={limit}"
            r   = requests.get(url, timeout=5)
            data = r.json()
            if not data:
                return []
            return sorted(data.values(), key=lambda x: x.get("time",""), reverse=True)
        except Exception as e:
            print(f"⚠ Get trades failed: {e}")
            return []
