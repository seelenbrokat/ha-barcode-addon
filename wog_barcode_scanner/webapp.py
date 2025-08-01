import logging
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path
import pymysql

app = Flask(__name__, static_folder='/config/www', template_folder='/config/www')
CORS(app)

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Lade Konfiguration aus Umgebungsvariablen (gesetzt von run.sh)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'mariadb'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'database': os.getenv('DB_NAME', 'homeassistant'),
    'table': os.getenv('DB_TABLE', 'wareneingang'),
    'sscc_column': os.getenv('SSCC_COLUMN', 'SSCCs')
}
logger.debug("DB-Konfiguration aus Umgebungsvariablen geladen.")

def get_db_connection():
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        logger.debug("DB-Verbindung hergestellt.")
        return conn
    except Exception as e:
        logger.error(f"DB-Verbindung fehlgeschlagen: {e}")
        return None

@app.route("/")
def index():
    if not Path("/config/www/index.html").exists():
        logger.error("index.html nicht gefunden.")
        return jsonify({"error": "Index-Seite nicht gefunden"}), 404
    return send_from_directory('/config/www', "index.html")

@app.route("/scan", methods=["POST"])
def scan():
    try:
        data = request.get_json()
        if data is None:
            logger.warning("Ungültiges JSON-Format.")
            return jsonify({"error": "Ungültiges JSON-Format"}), 400
        barcode = data.get("barcode")
        logger.debug(f"Barcode empfangen: {barcode}")
        if not barcode:
            logger.warning("Kein Barcode im Request.")
            return jsonify({"error": "Barcode fehlt"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Keine DB-Verbindung"}), 500

        try:
            with conn.cursor() as cursor:
                sql = f"SELECT * FROM {DB_CONFIG['table']} WHERE {DB_CONFIG['sscc_column']} LIKE %s LIMIT 1"
                cursor.execute(sql, ("%" + barcode + "%",))
                result = cursor.fetchone()
        finally:
            conn.close()

        if not result:
            logger.info(f"Kein Treffer für Barcode {barcode}")
            return jsonify({"found": False, "barcode": barcode})

        logger.debug(f"Treffer für Barcode {barcode}")
        return jsonify({"found": True, "barcode": barcode, "data": result})

    except Exception as e:
        logger.error(f"Fehler bei Scan: {e}", exc_info=True)
        return jsonify({"error": "Serverfehler"}), 500

@app.route('/<path:filename>')
def serve_static(filename):
    allowed_extensions = {'.html', '.js', '.css', '.png', '.jpg', '.jpeg'}
    if Path(filename).suffix not in allowed_extensions:
        logger.warning(f"Zugriff auf nicht erlaubte Datei: {filename}")
        return jsonify({"error": "Dateityp nicht erlaubt"}), 403
    if not Path(f"/config/www/{filename}").exists():
        logger.error(f"Datei nicht gefunden: {filename}")
        return jsonify({"error": "Datei nicht gefunden"}), 404
    return send_from_directory('/config/www', filename)

if __name__ == "__main__":
    logger.info("Starte Flask-Webserver für Home Assistant Add-on")
    app.run(host="0.0.0.0", port=5000, debug=False)
