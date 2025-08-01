#!/usr/bin/with-contenv bashio

# Home Assistant Add-on run script

# This script reads configuration options using bashio and starts
# the Python web application. Environment variables are exported
# so that the Python application can pick them up.

DB_HOST=$(bashio::config 'db_host')
DB_PORT=$(bashio::config 'db_port')
DB_USER=$(bashio::config 'db_user')
DB_PASSWORD=$(bashio::config 'db_password')
DB_NAME=$(bashio::config 'db_name')
DB_TABLE=$(bashio::config 'db_table')
SSCC_COLUMN=$(bashio::config 'sscc_column')
FTP_OUTPUT_DIR=$(bashio::config 'ftp_output_dir')
STATUS_TO_SCAN=$(bashio::config 'status_to_scan')

export DB_HOST
export DB_PORT
export DB_USER
export DB_PASSWORD
export DB_NAME
export DB_TABLE
export SSCC_COLUMN
export FTP_OUTPUT_DIR
export STATUS_TO_SCAN

# Starte webapp.py relativ zum Arbeitsverzeichnis
python3 /app/app/webapp.py
