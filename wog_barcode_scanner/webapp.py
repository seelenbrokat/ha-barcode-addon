import os
import logging
from flask import Flask, request, jsonify, send_from_directory
import pymysql
import json

# --- Log-Verzeichnis & Datei ---
LOG_DIR = "/tmp/logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "webapp.log")

def get_log_level_from_config():
    config_paths = ["/config/config.txt", "/config/config.json"]
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if path.endswith('.json'):
                        cfg = json.load(f)
                        lvl = cfg.get("log_level", "INFO").upper()
                        if lvl in ["DEBUG","INFO","WARNING","ERROR","CRITICAL"]:
                            return lvl
                    else:
                        # einfache txt config zeile: log_level=DEBUG
                        for line in f:
                            if line.lower().startswith("log_level="):
                                lvl = line.strip().split('=',1)[1].upper()
                                if lvl in ["DEBUG","INFO","WARNING","ERROR","CRITICAL"]:
                                    return lvl
            except Exception as e:
                # Hier ist noch kein logger, daher nur print
                print(f"Fehler beim Lesen des Log-Levels aus {path}: {e}")
    return "INFO"  # Default

# --- Logging-Konfiguration dynamisch ---
log_level_str = get_log_level_from_config()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Starte Webapp mit Logging-Level: {log_level_str}")

app = Flask(__name__, static_folder='.', template_folder='.')

def read_db_config():
    config_paths = ["/config/config.txt", "/config/config.json"]
    config = None
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if path.endswith('.json'):
                        config = json.load(f)
                        logger.info(f"DB-Konfig aus JSON geladen: {path}")
                    else:
                        config = {}
                        for line in f:
                            if '=' in line:
                                k, v = line.strip().split('=', 1)
                                config[k.strip()] = v.strip()
                        logger.info(f"DB-Konfig aus TXT geladen: {path}")
                break
            except Exception as e:
                logger.error(f"Fehler beim Laden der DB-Konfig aus {path}: {e}", exc_info=True)
    if not config:
        logger.error("Keine gültige DB-Konfiguration gefunden.")
    return config

def get_db_conn():
    cfg = read_db_config()
    if not cfg:
        logger.error("DB-Konfiguration fehlt oder ungültig.")
        return None

    try:
        conn = pymysql.connect(
            host=cfg.get("host"),
            port=int(cfg.get("port", 3306)),
            user=cfg.get("user"),
            password=cfg.get("password"),
            database=cfg.get("database"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        logger.info("Erfolgreich mit der MariaDB verbunden.")
        return conn
    except Exception as e:
        logger.error(f"Fehler beim Verbinden mit der MariaDB: {e}", exc_info=True)
        return None

last_scans = []

@app.route("/")
def index():
    logger.info("Index-Seite angefordert.")
    return send_from_directory('.', "index.html")

@app.route("/scan", methods=["POST"])
def scan():
    try:
        data = request.get_json(force=True)
        barcode = data.get("barcode")
        logger.info(f"Scan-Anfrage empfangen für Barcode: {barcode}")

        if not barcode:
            logger.warning("Kein Barcode im Request gefunden.")
            return jsonify({"error": "Kein Barcode angegeben"}), 400

        conn = get_db_conn()
        if not conn:
            logger.error("Keine DB-Verbindung möglich.")
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
            logger.warning(f"Kein Datensatz für Barcode '{barcode}' gefunden.")
            result = {"found": False, "barcode": barcode}
        else:
            result = {"found": True, "barcode": barcode, "data": row}

        last_scans.insert(0, {"barcode": barcode, "result": result})
        if len(last_scans) > 10:
            last_scans.pop()

        logger.info(f"Scan-Ergebnis für '{barcode}': {result}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Fehler bei Scan-API: {e}", exc_info=True)
        return jsonify({"error": "Interner Serverfehler"}), 500

@app.route("/last_scans", methods=["GET"])
def last_scans_api():
    try:
        logger.info("Letzte Scans angefragt.")
        return jsonify(last_scans)
    except Exception as e:
        logger.error(f"Fehler bei /last_scans: {e}", exc_info=True)
        return jsonify([])

@app.route('/<path:filename>')
def serve_static(filename):
    logger.info(f"Statische Datei angefragt: {filename}")
    return send_from_directory('.', filename)

if __name__ == "__main__":
    logger.info("Starte Flask Webserver...")
    app.run(host="0.0.0.0", port=5000)
