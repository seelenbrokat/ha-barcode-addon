import os
import logging
from flask import Flask, request, jsonify, send_from_directory
import pymysql
import json

# --- Log-Verzeichnis & Datei ---
LOG_DIR = "/tmp/logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "webapp.log")

# --- Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG,  # Maximal: DEBUG
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.debug("Starte Webapp mit LOG-Level DEBUG (maximal).")

app = Flask(__name__, static_folder='.', template_folder='.')

# --- DB Konfiguration aus JSON (Standard Pfad) ---
def read_db_config():
    config_path = "/config/config.json"
    if not os.path.exists(config_path):
        logger.error(f"DB-Konfigdatei nicht gefunden unter {config_path}")
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            logger.debug(f"DB-Konfig geladen aus {config_path}: {config}")
            return config
    except Exception as e:
        logger.error(f"Fehler beim Laden der DB-Konfiguration: {e}", exc_info=True)
        return None

# --- DB Verbindung ---
def get_db_conn():
    cfg = read_db_config()
    if not cfg:
        logger.error("DB-Konfiguration fehlt oder ungültig.")
        return None
    try:
        conn = pymysql.connect(
            host=cfg.get("db_host"),
            port=int(cfg.get("db_port", 3306)),
            user=cfg.get("db_user"),
            password=cfg.get("db_password"),
            database=cfg.get("db_name"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        logger.debug("Erfolgreich mit der MariaDB verbunden.")
        return conn
    except Exception as e:
        logger.error(f"Fehler beim Verbinden mit der MariaDB: {e}", exc_info=True)
        return None

# --- Letzte Scans im Speicher ---
last_scans = []

# --- Index-Seite ---
@app.route("/")
def index():
    logger.info("Index-Seite angefordert.")
    return send_from_directory('.', "index.html")

# --- Scan-API ---
@app.route("/scan", methods=["POST"])
def scan():
    try:
        data = request.get_json(force=True)
        barcode = data.get("barcode")
        logger.debug(f"Scan-Anfrage empfangen mit Barcode: {barcode}")

        if not barcode:
            logger.warning("Kein Barcode im Request gefunden.")
            return jsonify({"error": "Kein Barcode angegeben"}), 400

        conn = get_db_conn()
        if not conn:
            logger.error("Keine DB-Verbindung möglich.")
            return jsonify({"error": "DB-Verbindung fehlgeschlagen"}), 500

        with conn.cursor() as cur:
            table = read_db_config().get("db_table", "wareneingang")
            sscc_column = read_db_config().get("sscc_column", "SSCCs")

            sql = f"""
                SELECT *, Quantity AS Colli
                FROM {table}
                WHERE {sscc_column} LIKE %s
                ORDER BY ID DESC LIMIT 1
            """
            like_param = f"%{barcode}%"
            logger.debug(f"SQL-Abfrage: {sql} mit Param: {like_param}")
            cur.execute(sql, (like_param,))
            row = cur.fetchone()
        conn.close()

        if not row:
            logger.info(f"Kein Datensatz für Barcode '{barcode}' gefunden.")
            result = {"found": False, "barcode": barcode}
        else:
            result = {"found": True, "barcode": barcode, "data": row}

        last_scans.insert(0, {"barcode": barcode, "result": result})
        if len(last_scans) > 10:
            last_scans.pop()

        logger.debug(f"Scan-Ergebnis: {result}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Fehler bei Scan-API: {e}", exc_info=True)
        return jsonify({"error": "Interner Serverfehler"}), 500

# --- API letzte Scans ---
@app.route("/last_scans", methods=["GET"])
def last_scans_api():
    try:
        logger.debug("Letzte Scans angefragt.")
        return jsonify(last_scans)
    except Exception as e:
        logger.error(f"Fehler bei /last_scans: {e}", exc_info=True)
        return jsonify([])

# --- Statische Dateien (index.html, CSS, JS, etc) ---
@app.route('/<path:filename>')
def serve_static(filename):
    logger.debug(f"Statische Datei angefragt: {filename}")
    return send_from_directory('.', filename)

if __name__ == "__main__":
    logger.info("Starte Flask Webserver...")
    app.run(host="0.0.0.0", port=5000)
