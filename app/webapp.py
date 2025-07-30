"""
Web application for the Home Assistant barcode scanner add-on.

This application provides a simple web interface for scanning SSCC
barcodes using a live camera feed (powered by QuaggaJS) or manual
entry. When a barcode is submitted, the app queries a MariaDB
database for matching information and displays the result. A second
view allows a barcode to be scanned and a status update written
to an XML file in a configured directory, which can be served via
FTP from Home Assistant.

Configuration options are supplied via environment variables that
are populated from the add-on's config.json. See run.sh for the
mapping of these variables.
"""

from flask import Flask, render_template, request, redirect, url_for, flash
import os
import pymysql
from datetime import datetime
import xml.etree.ElementTree as ET

app = Flask(__name__)
app.secret_key = 'replace-with-a-secret-key'  # Required for flash messages


def get_db_connection():
    """Return a connection to the MariaDB database using environment vars."""
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 3306)),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', ''),
        cursorclass=pymysql.cursors.DictCursor
    )


@app.route('/', methods=['GET', 'POST'])
def index():
    """Main view for scanning SSCC barcodes and displaying results."""
    if request.method == 'POST':
        barcode = request.form['barcode']
        record = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                table = os.getenv('DB_TABLE', 'shipments')
                sscc_column = os.getenv('SSCC_COLUMN', 'sscc')
                sql = f"SELECT * FROM `{table}` WHERE `{sscc_column}`=%s"
                cursor.execute(sql, (barcode,))
                record = cursor.fetchone()
        except Exception as err:
            flash(f'Datenbankfehler: {err}', 'error')
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return render_template('result.html', record=record, barcode=barcode)
    return render_template('index.html')


@app.route('/status', methods=['GET', 'POST'])
def status():
    """View for scanning a barcode and writing a status XML file."""
    status_to_scan = os.getenv('STATUS_TO_SCAN', 'status')
    if request.method == 'POST':
        barcode = request.form['barcode']
        # Build XML structure
        root = ET.Element('status_update')
        ET.SubElement(root, 'barcode').text = barcode
        ET.SubElement(root, 'status').text = status_to_scan
        ET.SubElement(root, 'timestamp').text = datetime.utcnow().isoformat() + 'Z'
        xml_string = ET.tostring(root, encoding='utf-8', method='xml')
        output_dir = os.getenv('FTP_OUTPUT_DIR', '/data')
        os.makedirs(output_dir, exist_ok=True)
        filename = f'{barcode}_{int(datetime.utcnow().timestamp())}.xml'
        filepath = os.path.join(output_dir, filename)
        try:
            with open(filepath, 'wb') as f:
                f.write(xml_string)
            flash(f'Status für {barcode} wurde gespeichert.', 'success')
        except Exception as err:
            flash(f'Fehler beim Schreiben der XML-Datei: {err}', 'error')
        return redirect(url_for('status'))
    return render_template('status.html', status=status_to_scan)


@app.route('/settings')
def settings():
    """Display the current configuration options."""
    options = {
        'db_host': os.getenv('DB_HOST'),
        'db_port': os.getenv('DB_PORT'),
        'db_user': os.getenv('DB_USER'),
        'db_name': os.getenv('DB_NAME'),
        'db_table': os.getenv('DB_TABLE'),
        'sscc_column': os.getenv('SSCC_COLUMN'),
        'ftp_output_dir': os.getenv('FTP_OUTPUT_DIR'),
        'status_to_scan': os.getenv('STATUS_TO_SCAN')
    }
    return render_template('settings.html', options=options)


if __name__ == '__main__':
    # When running standalone (e.g. during development) bind to 0.0.0.0
    app.run(host='0.0.0.0', port=5000)
