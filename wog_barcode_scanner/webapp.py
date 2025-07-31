import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, send_from_directory, abort
import pymysql
import json

# --- Logging Setup ---
LOG_DIR = "/config/logs"
LOG_FILE = os.path.join(LOG_DIR, "webapp.log")
os.makedirs(LOG_DIR, exist_ok=True)

handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding='utf-8')
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        handler,
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("webapp")
logger.info("WebApp gestartet. Logging läuft!")

app = Flask(__name__, static_folder='.', template_folder='.')

# --- Config lesen ---
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
                logger.info(f"Konfig geladen: {path}")
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
        logger.info("Erfolgreich mit MariaDB verbunden")
        return conn
    except Exception as e:
        logger.error(f"Fehler beim Verbinden mit MariaDB: {e}", exc_info=True)
        return None

last_scans = []

# --- Index-Seite (Barcode Web UI) ---
@app.route("/")
def index():
    try:
        logger.info("Indexseite angefragt")
        return send_from_directory('.', "index.html")
    except Exception as e:
        logger.error(f"Fehler beim Bereitstellen von index.html: {e}", exc_info=True)
        return abort(500, description="index.html fehlt oder nicht lesbar")

# --- API: Barcode scannen ---
@app.route("/scan", methods=["POST"])
def scan():
    try:
        data = request.get_json(force=True)
        barcode = data.get("barcode")
        logger.info(f"Scan-Anfrage: {barcode}")

        conn = get_db_conn()
        if not conn:
            logger.error("DB-Verbindung fehlgeschlagen.")
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
        logger.info(f"Scan-Ergebnis: {result}")
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
    try:
        return send_from_directory('.', filename)
    except Exception as e:
        logger.error(f"Fehler beim Bereitstellen von {filename}: {e}", exc_info=True)
        return abort(404, description=f"{filename} fehlt")

if __name__ == "__main__":
    logger.info("Webapp wird gestartet...")
    app.run(host="0.0.0.0", port=5000)
