import sys
import logging
import json
import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path
import pymysql
from datetime import datetime
import xml.etree.ElementTree as ET
from ftplib import FTP_TLS

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='/config/www', template_folder='/config/www')
CORS(app)  # Aktiviere CORS für Ingress

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

# Mapping Status zu Number
STATUS_MAPPING = {
    "Hallenscan": "1",
    "Wareneingang": "2",
    "Warenausgang": "3",
    "Retoure": "4"
}

def create_sscc_xml(sscc, status, user, location):
    # Holt OrderNumber & ConsignmentNumber
    conn = get_db_connection()
    order_nr, consignment_nr = "", ""
    try:
        if conn:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT *
                    FROM {DB_CONFIG['table']}
                    WHERE FIND_IN_SET(%s, REPLACE({DB_CONFIG['sscc_column']}, ', ', ',')) > 0
                    LIMIT 1
                """
                cursor.execute(sql, (sscc,))
                row = cursor.fetchone()
                if row:
                    order_nr = str(row.get("OrderNumber", ""))
                    consignment_nr = str(row.get("ConsignmentNumber", ""))
    finally:
        if conn:
            conn.close()

    workflow_num = f"{order_nr}.{consignment_nr}" if order_nr and consignment_nr else ""
    now = datetime.now()
    status_time = now.strftime("%Y-%m-%dT%H:%M:%S")
    send_date = status_time
    export_ref = str(uuid.uuid4())

    ns = "http://soloplan.de/ssccimport.v1"
    ET.register_namespace('', ns)
    root = ET.Element(f"{{{ns}}}SsccCurrentData")

    # Header
    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "SendDate").text = send_date
    ET.SubElement(header, "ExportItemReference").text = export_ref

    # SsccCurrent
    sc = ET.SubElement(root, "SsccCurrent")
    ET.SubElement(sc, "Sendungsnummer_Workflow").text = workflow_num
    ET.SubElement(sc, "StatusTime").text = status_time
    ET.SubElement(sc, "Number").text = STATUS_MAPPING.get(status, "1")
    ET.SubElement(sc, "Code").text = sscc
    ET.SubElement(sc, "Location").text = location
    ET.SubElement(sc, "User").text = user

    filename = f"ssccstatus_{sscc}_{now.strftime('%Y%m%dT%H%M%S')}.xml"
    filepath = os.path.join(XML_DIR, filename)
    ET.ElementTree(root).write(filepath, encoding='utf-8', xml_declaration=True)
    logger.debug(f"Status-XML erzeugt: {filepath}")
    return filepath, filename

def upload_ftp(filepath, filename):
    try:
        if not FTP_CONFIG["host"] or not FTP_CONFIG["user"] or not FTP_CONFIG["pass"]:
            logger.warning("FTP-Daten nicht vollständig konfiguriert.")
            return False, "FTP-Daten fehlen."
        with FTP_TLS(FTP_CONFIG["host"]) as ftp:
            ftp.login(user=FTP_CONFIG["user"], passwd=FTP_CONFIG["pass"])
            ftp.prot_p()
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
    try:
        data = request.get_json(silent=True)
        sscc = data.get("sscc", "").strip()
        status = data.get("status", "Hallenscan")
        user = data.get("user", "3")
        location = data.get("location", "ikea halle")
        if not sscc:
            return jsonify({"ok": False, "error": "Kein SSCC übergeben"})
        filepath, filename = create_sscc_xml(sscc, status, user, location)
        ok, msg = upload_ftp(filepath, filename)
        return jsonify({"ok": ok, "error": None if ok else msg})
    except Exception as e:
        logger.error(f"Fehler in /scan_status: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/set_status", methods=["POST"])
def set_status():
    try:
        data = request.get_json(silent=True)
        sscc = data.get("sscc", "").strip()
        status = data.get("status", "Hallenscan")
        user = data.get("user", "3")
        location = data.get("location", "ikea halle")
        if not sscc:
            return jsonify({"ok": False, "error": "Kein SSCC übergeben"})
        filepath, filename = create_sscc_xml(sscc, status, user, location)
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
