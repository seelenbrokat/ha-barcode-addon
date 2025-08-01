import sys
import logging
import json
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path
import pymysql
from datetime import datetime
import xml.etree.ElementTree as ET
from ftplib import FTP_TLS  # ← NUR HIER: FTPS verwenden!

# Logging explizit auf stdout für Home Assistant Add-on!
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='/config/www', template_folder='/config/www')
CORS(app)  # Aktiviere CORS für Ingress

# Lade Konfiguration aus Home Assistant Add-on-Options
CONFIG_FILE = '/data/options.json'
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    DB_CONFIG = {
        'host': config.get('db_host', 'mariadb'),
        'port': int(config.get('db_port', 3306)),
        'user': config.get('db_user', 'root'),
        'password': config.get('db_password', 'password'),
        'database': config.get('db_name', 'homeassistant'),
        'table': config.get('db_table', 'wareneingang'),
        'sscc_column': config.get('sscc_column', 'SSCCs')
    }
    FTP_CONFIG = {
        'host': config.get('ftp_host', ''),
        'user': config.get('ftp_user', ''),
        'pass': config.get('ftp_pass', ''),
        'dir': config.get('ftp_dir', '/')
    }
    XML_DIR = config.get('xml_dir', '/share/barcode_status_xml/')
    logger.debug("Konfiguration aus /data/options.json geladen.")
else:
    logger.warning("Keine Konfigurationsdatei gefunden. Verwende Standardwerte.")
    DB_CONFIG = {
        'host': 'mariadb',
        'port': 3306,
        'user': 'root',
        'password': 'password',
        'database': 'homeassistant',
        'table': 'wareneingang',
        'sscc_column': 'SSCCs'
    }
    FTP_CONFIG = {
        'host': '',
        'user': '',
        'pass': '',
        'dir': '/'
    }
    XML_DIR = '/share/barcode_status_xml/'

os.makedirs(XML_DIR, exist_ok=True)

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
    # Gibt die index.html zurück
    if not Path("/config/www/index.html").exists():
        logger.error("index.html nicht gefunden.")
        return jsonify({"error": "Index-Seite nicht gefunden"}), 404
    return send_from_directory('/config/www', "index.html")

@app.route("/scan", methods=["POST"])
def scan():
    # Standard-Scan-Modus (unverändert, robustes JSON-Parsing!)
    try:
        data = request.get_json(silent=True)
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
            logger.error("Fehler: Keine DB-Verbindung bei Scan!")
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

def create_status_xml(sscc, status):
    # Erzeuge Status-XML
    root = ET.Element("Status")
    ET.SubElement(root, "SSCC").text = sscc
    ET.SubElement(root, "Status").text = status
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    ET.SubElement(root, "Timestamp").text = timestamp

    filename = f"status_{sscc}_{datetime.now().strftime('%Y%m%dT%H%M%S')}.xml"
    filepath = os.path.join(XML_DIR, filename)
    ET.ElementTree(root).write(filepath, encoding='utf-8', xml_declaration=True)
    logger.debug(f"Status-XML erzeugt: {filepath}")
    return filepath, filename

def upload_ftp(filepath, filename):
    # Übertrage Datei per FTPS (explizit TLS!)
    try:
        if not FTP_CONFIG["host"] or not FTP_CONFIG["user"] or not FTP_CONFIG["pass"]:
            logger.warning("FTP-Daten nicht vollständig konfiguriert.")
            return False, "FTP-Daten fehlen."
        with FTP_TLS(FTP_CONFIG["host"]) as ftp:          # FTPS verwenden!
            ftp.login(user=FTP_CONFIG["user"], passwd=FTP_CONFIG["pass"])
            ftp.prot_p()                                 # Verschlüsselten Datentransfer aktivieren!
            ftp.cwd(FTP_CONFIG.get("dir", "/"))
            with open(filepath, "rb") as f:
                ftp.storbinary(f"STOR {filename}", f)
        logger.info(f"Status-XML via FTPS übertragen: {filename}")
        return True, "Übertragen"
    except Exception as e:
        logger.error(f"FTP-Fehler: {e}")
        return False, str(e)

@app.route("/scan_status", methods=["POST"])
def scan_status():
    # Hallenscan-Modus: Status setzen, XML, FTP
    try:
        data = request.get_json(silent=True)
        sscc = data.get("sscc", "").strip()
        status = data.get("status", "Hallenscan")
        if not sscc:
            return jsonify({"ok": False, "error": "Kein SSCC übergeben"})
        filepath, filename = create_status_xml(sscc, status)
        ok, msg = upload_ftp(filepath, filename)
        return jsonify({"ok": ok, "error": None if ok else msg})
    except Exception as e:
        logger.error(f"Fehler in /scan_status: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/set_status", methods=["POST"])
def set_status():
    # Manueller Modus: Status setzen, XML, FTP
    try:
        data = request.get_json(silent=True)
        sscc = data.get("sscc", "").strip()
        status = data.get("status", "Hallenscan")
        if not sscc:
            return jsonify({"ok": False, "error": "Kein SSCC übergeben"})
        filepath, filename = create_status_xml(sscc, status)
        ok, msg = upload_ftp(filepath, filename)
        return jsonify({"ok": ok, "error": None if ok else msg})
    except Exception as e:
        logger.error(f"Fehler in /set_status: {e}")
        return jsonify({"ok": False, "error": str(e)})

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
