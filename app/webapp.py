from flask import Flask, request, jsonify, send_from_directory
import pymysql
import configparser
import os

app = Flask(__name__, static_folder=".", static_url_path="")  # "." = aktuelles Verzeichnis

def get_config():
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(__file__), 'config.txt'))
    return config

def get_db_connection():
    config = get_config()
    dbconf = config['Database']
    return pymysql.connect(
        host=dbconf.get('Host'),
        port=int(dbconf.get('Port', 3306)),
        user=dbconf.get('User'),
        password=dbconf.get('Password'),
        database=dbconf.get('Database'),
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route("/")
def home():
    # Liefert die index.html direkt aus dem aktuellen Verzeichnis
    return send_from_directory(app.static_folder, "index.html")

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
