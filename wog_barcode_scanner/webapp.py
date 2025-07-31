from flask import Flask, request, jsonify, send_from_directory
import pymysql
import os
import logging
import traceback

# Logging-Setup: Alles landet in stdout (sichtbar in HA-Addon-Log)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)

app = Flask(__name__, static_folder=".", static_url_path="")

def get_db_connection():
    try:
        conn = pymysql.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 3306)),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "homeassistant"),
            cursorclass=pymysql.cursors.DictCursor
        )
        logging.info("MariaDB connection established.")
        return conn
    except Exception as e:
        logging.error("Fehler beim Verbinden zur MariaDB: %s", e)
        logging.error(traceback.format_exc())
        raise

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/scan")
def api_scan():
    barcode = request.args.get("barcode", "")
    if not barcode:
        logging.warning("Scan-API ohne Barcode aufgerufen!")
        return jsonify({"found": False, "error": "No barcode provided."}), 400
    try:
        conn = get_db_connection()
        try:
            table = os.environ.get("DB_TABLE", "wareneingang")
            sscc_col = os.environ.get("SSCC_COLUMN", "SSCCs")
            sql = f"SELECT Recipient, DeliveryDate, OrderNumber, Quantity FROM {table} WHERE {sscc_col} = %s LIMIT 1"
            with conn.cursor() as cur:
                cur.execute(sql, (barcode,))
                row = cur.fetchone()
                if row:
                    logging.info(f"Scan-API: Barcode {barcode} gefunden: {row}")
                    return jsonify({"found": True, **row})
                else:
                    logging.info(f"Scan-API: Barcode {barcode} NICHT gefunden.")
                    return jsonify({"found": False, "error": "Not found"}), 404
        finally:
            conn.close()
    except Exception as e:
        logging.error(f"Fehler in Scan-API für Barcode {barcode}: {e}")
        logging.error(traceback.format_exc())
        return jsonify({"found": False, "error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
