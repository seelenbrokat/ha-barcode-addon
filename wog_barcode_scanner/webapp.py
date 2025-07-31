from flask import Flask, request, jsonify, send_from_directory
import pymysql
import os

app = Flask(__name__, static_folder=".", static_url_path="")

def get_db_connection():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "homeassistant"),
        cursorclass=pymysql.cursors.DictCursor
    )

# Liefert index.html direkt aus /app
@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

# API-Endpoint für Scan
@app.route("/api/scan")
def api_scan():
    barcode = request.args.get("barcode", "")
    if not barcode:
        return jsonify({"found": False})
    conn = get_db_connection()
    try:
        table = os.environ.get("DB_TABLE", "wareneingang")
        sscc_col = os.environ.get("SSCC_COLUMN", "SSCCs")
        sql = f"SELECT Recipient, DeliveryDate, OrderNumber, Quantity FROM {table} WHERE {sscc_col} = %s LIMIT 1"
        with conn.cursor() as cur:
            cur.execute(sql, (barcode,))
            row = cur.fetchone()
            if row:
                return jsonify({"found": True, **row})
            else:
                return jsonify({"found": False})
    finally:
        conn.close()

# Optional: Alle weiteren statischen Dateien (CSS/JS/Bilder) auch aus /app bereitstellen
@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
