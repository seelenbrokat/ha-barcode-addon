import os
import logging
from flask import Flask, request, jsonify, send_from_directory
import pymysql
import json

# --- Logging einrichten ---
LOG_DIR = "/tmp/logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "webapp.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', template_folder='.')

# --- MariaDB Verbindung aus config.txt oder config.json ---
def read_db_config():
    config_paths = ["/config/config.txt", "/config/config.json"]
    config = None
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if path.endswith('.json'):
                        config = json.load(f)
                    else:
                        config = {}
                        for line in f:
                            if '=' in line:
                                k, v = line.strip().split('=', 1)
                                config[k.strip()] = v.strip()
            except Exception as e:
                logger.error(f"Fehler beim Laden der DB-Konfig aus {path}: {e}", exc_info=True)
    if not config:
        logger.error("Keine gültige DB-Konfiguration gefunden.")
    return config

def get_db_conn():
    cfg = read_db_config()
    try:
        conn = pymysql.connect(
            host=cfg.get("host"),
            port=int(cfg.get("port", 3306)),
            user=cfg.get("user"),
            password=cfg.get("password"),
            database=cfg.get("database"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"Fehler beim Verbinden mit der MariaDB: {e}", exc_info=True)
        return None

# --- Letzte Scans merken (in RAM für Demo) ---
last_scans = []

# --- Index-Seite ---
@app.route("/")
def index():
    return send_from_directory('.', "index.html")

# --- API: Barcode scannen ---
@app.route("/scan", methods=["POST"])
def scan():
    try:
        data = request.get_json(force=True)
        barcode = data.get("barcode")
        logger.info(f"Scan-Anfrage empfangen für Barcode: {barcode}")

        conn = get_db_conn()
        if not conn:
            logger.error("Keine DB-Verbindung.")
            return jsonify({"error": "DB-Verbindung fehlgeschlagen"}), 500

        with conn.cursor() as cur:
            sql = """
                SELECT *, Quantity AS Colli
                FROM wareneingang
                WHERE SSCCs LIKE %s
                ORDER BY ID DESC LIMIT 1
            """
            like_param = f"%{barcode}%"
            cur.execute(sql, (like_param,))
            row = cur.fetchone()
        conn.close()

        if not row:
            logger.warning(f"Kein Datensatz für Barcode {barcode} gefunden.")
            result = {"found": False, "barcode": barcode}
        else:
            result = {"found": True, "barcode": barcode, "data": row}

        last_scans.insert(0, {"barcode": barcode, "result": result})
        if len(last_scans) > 10:
            last_scans.pop()

        logger.info(f"Scan-Ergebnis für {barcode}: {result}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Fehler bei Scan-API: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# --- API: Letzte Scans abrufen ---
@app.route("/last_scans", methods=["GET"])
def last_scans_api():
    try:
        return jsonify(last_scans)
    except Exception as e:
        logger.error(f"Fehler bei /last_scans: {e}", exc_info=True)
        return jsonify([])

# --- Statische Dateien bereitstellen ---
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

# --- Start ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
