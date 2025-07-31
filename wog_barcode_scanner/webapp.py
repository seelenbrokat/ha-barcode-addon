import os
import logging
import sys
from flask import Flask, request, render_template, jsonify
import pymysql
import traceback

# -------- LOGGING EINRICHTEN --------
LOG_DIR = "/data/logs"
LOG_FILE = os.path.join(LOG_DIR, "webapp.log")
os.makedirs(LOG_DIR, exist_ok=True)

formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = []  # Verhindert doppelte Einträge
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logging.info("WOG Barcode Scanner Add-on gestartet!")

# -------- FLASK-APP INITIALISIEREN --------
# "." = aktueller Ordner, in dem webapp.py UND index.html liegen
app = Flask(__name__, template_folder=".")

# -------- HILFSFUNKTION FÜR DB-CONNECT --------
def get_db_connection():
    try:
        dbhost = os.environ.get('DB_HOST', 'mariadb')
        dbuser = os.environ.get('DB_USER', 'root')
        dbpass = os.environ.get('DB_PASSWORD', 'geheim')
        dbname = os.environ.get('DB_NAME', 'wareneingang')
        conn = pymysql.connect(
            host=dbhost,
            user=dbuser,
            password=dbpass,
            database=dbname,
            cursorclass=pymysql.cursors.DictCursor
        )
        logging.info(f"DB-Verbindung zu {dbhost}/{dbname} als {dbuser} erfolgreich.")
        return conn
    except Exception as e:
        logging.error(f"DB-Verbindung fehlgeschlagen: {e}")
        logging.error(traceback.format_exc())
        raise

# -------- ROUTES --------
@app.route("/", methods=["GET"])
def index():
    logging.info("Index-Seite aufgerufen.")
    try:
        return render_template("index.html")
    except Exception as e:
        logging.error(f"Fehler beim Rendern der Index-Seite: {e}")
        logging.error(traceback.format_exc())
        return "Fehler beim Laden der Seite", 500

@app.route("/api/scan", methods=["POST"])
def scan_barcode():
    try:
        data = request.get_json()
        barcode = data.get("barcode")
        logging.info(f"Scan-Request: barcode={barcode}")

        conn = get_db_connection()
        with conn.cursor() as cur:
            sql = """
                SELECT *
                FROM wareneingang
                WHERE SSCCs LIKE %s
                ORDER BY ImportTimestamp DESC
                LIMIT 1
            """
            cur.execute(sql, (f"%{barcode}%",))
            result = cur.fetchone()
            if not result:
                logging.warning(f"Barcode {barcode} nicht gefunden.")
                return jsonify({"status": "not_found", "message": "Barcode nicht gefunden."}), 404

            # Colli-Anzahl (Quantity) ermitteln
            collis = result.get("Quantity", "n/a")
            logging.info(f"Barcode gefunden: {barcode}, Collis={collis}")
            return jsonify({"status": "ok", "data": result, "collis": collis}), 200
    except Exception as e:
        logging.error(f"Fehler beim Scan: {e}")
        logging.error(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

# -------- ERROR HANDLING --------
@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled Exception: {e}")
    logging.error(traceback.format_exc())
    return jsonify({"status": "error", "message": str(e)}), 500

# -------- START --------
if __name__ == "__main__":
    logging.info("Flask-Server wird gestartet auf 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
