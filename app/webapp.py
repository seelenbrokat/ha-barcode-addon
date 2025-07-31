from flask import Flask, request, jsonify
import pymysql

app = Flask(__name__)

def get_db_connection():
    return pymysql.connect(
        host="DEIN_MARIADB_HOST",
        user="DEIN_DB_USER",
        password="DEIN_DB_PASS",
        database="DEINE_DATENBANK",
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route("/api/scan")
def api_scan():
    barcode = request.args.get("barcode", "")
    if not barcode:
        return jsonify({"found": False})
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = "SELECT Recipient, DeliveryDate, OrderNumber, Quantity FROM wareneingang WHERE SSCCs = %s LIMIT 1"
            cur.execute(sql, (barcode,))
            row = cur.fetchone()
            if row:
                return jsonify({"found": True, **row})
            else:
                return jsonify({"found": False})
    finally:
        conn.close()
