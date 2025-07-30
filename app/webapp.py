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
def menu():
    """
    Landing page presenting a simple menu for selecting either the status
    update or the shipment info view. This replaces the previous index
    page which immediately started the scanner. The menu links lead to
    dedicated routes for each function.
    """
    return render_template('menu.html')


@app.route('/info', methods=['GET', 'POST'])
def info():
    """
    View for retrieving shipment information. Users can scan an SSCC
    barcode or enter it manually. On POST the database is queried and
    the result displayed. This essentially replaces the previous index
    view.
    """
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
    return render_template('info.html')


@app.route('/status', methods=['GET', 'POST'])
def status():
    """
    View for setting a status on an SSCC. On GET the user chooses a
    status from a dropdown and optionally scans or enters a barcode.
    On POST the selected status and barcode are used to generate an
    XML file in the configured output directory. The resulting file
    follows the structure expected by the Soloplan integration.
    """
    # Load available statuses from the JSON file shipped with the add-on
    statuses = []
    statuses_path = os.path.join(os.path.dirname(__file__), 'statuses.json')
    try:
        import json
        with open(statuses_path, 'r', encoding='utf-8') as fh:
            statuses = json.load(fh)
    except Exception:
        statuses = []
    if request.method == 'POST':
        barcode = request.form['barcode']
        selected_code = request.form.get('status')
        # Build XML structure according to sample; always use constant scan point 'ikea'
        root = ET.Element('SsccStatus', attrib={
            'xmlns': 'http://www.soloplan.de/StdTelematics',
            'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        })
        # For demo purposes, order number and item number are placeholders
        ET.SubElement(root, 'TransportOrderNumber').text = ''
        ET.SubElement(root, 'ItemNumber').text = '1'
        ssccs = ET.SubElement(root, 'Ssccs')
        sscc = ET.SubElement(ssccs, 'Sscc')
        ET.SubElement(sscc, 'Code').text = barcode
        ET.SubElement(sscc, 'Status').text = selected_code or ''
        ET.SubElement(sscc, 'StatusTimestamp').text = datetime.utcnow().isoformat(timespec='seconds')
        ET.SubElement(sscc, 'ScanPoint').text = 'ikea'
        ET.SubElement(sscc, 'CarloFieldValues')
        xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        output_dir = os.getenv('FTP_OUTPUT_DIR', '/data')
        os.makedirs(output_dir, exist_ok=True)
        filename = f'{barcode}_{int(datetime.utcnow().timestamp())}.xml'
        filepath = os.path.join(output_dir, filename)
        try:
            with open(filepath, 'wb') as f:
                f.write(xml_string)
            flash(f'Status {selected_code} für {barcode} wurde gespeichert.', 'success')
        except Exception as err:
            flash(f'Fehler beim Schreiben der XML-Datei: {err}', 'error')
        return redirect(url_for('status'))
    # Determine default status to scan from environment for heading
    status_to_scan = os.getenv('STATUS_TO_SCAN', '')
    return render_template('status.html', statuses=statuses, current_status=status_to_scan)


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