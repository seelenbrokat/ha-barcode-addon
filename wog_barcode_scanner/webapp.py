import os
import logging
from flask import Flask, request, jsonify, send_from_directory
import pymysql
import json

# Logging Setup
LOG_DIR = "/tmp/logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "webapp.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', template_folder='.')

# DB config statisch hier, kannst du auch aus Config-Datei lesen
DB_CONFIG = {
    "host": "mariadb",
    "port": 3306,
    "user": "root",
    "password": "password",
    "database": "homeassistant"
}

def get_db_conn():
    try:
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        logger.debug("MariaDB Verbindung hergestellt.")
        return conn
    except Exception as e:
        logger.error(f"Fehler bei DB-Verbindung: {e}", exc_info=True)
        return None

@app.route("/")
def index():
    logger.debug("Index-Seite angefordert.")
    return send_from_directory('.', "index.html")

@app.route("/scan", methods=["POST"])
def scan():
    try:
        data = request.get_json(force=True)
        barcode = data.get("barcode")
        logger.debug(f"Scan-Anfrage erhalten: {barcode}")

        if not barcode:
            logger.warning("Kein Barcode übergeben.")
            return jsonify({"error": "Kein Barcode übergeben"}), 400

        conn = get_db_conn()
        if not conn:
            return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500

        with conn.cursor() as cur:
            # Einfach nur Empfängername auslesen, Beispiel
            sql = f"""
                SELECT EmpfName1 
                FROM wareneingang 
                WHERE SSCCs LIKE %s
                ORDER BY ID DESC
                LIMIT 1
            """
            cur.execute(sql, (f"%{barcode}%",))
            row = cur.fetchone()

        conn.close()

        if not row:
            logger.info(f"Kein Datensatz für Barcode {barcode} gefunden.")
            return jsonify({"found": False, "barcode": barcode})

        logger.info(f"Datensatz gefunden für Barcode {barcode}: {row}")
        return jsonify({"found": True, "barcode": barcode, "data": row})

    except Exception as e:
        logger.error(f"Fehler im Scan-Endpunkt: {e}", exc_info=True)
        return jsonify({"error": "Interner Serverfehler"}), 500

@app.route('/<path:filename>')
def serve_static(filename):
    logger.debug(f"Statische Datei angefragt: {filename}")
    return send_from_directory('.', filename)

if __name__ == "__main__":
    logger.info("Starte Flask Webserver")
    app.run(host="0.0.0.0", port=5000)
