# Verwende ein Home Assistant Add-on-Basisimage mit bashio
FROM ghcr.io/home-assistant/raspberrypi3-homeassistant:2025.8.0

WORKDIR /app
COPY . /app

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir \
    Flask==3.0.0 \
    PyMySQL==1.1.1 \
    flask_cors==4.0.1

# Kopiere index.html nach /config/www
RUN mkdir -p /config/www && cp /app/index.html /config/www/index.html

EXPOSE 5000

# Starte mit run.sh
CMD ["sh", "run.sh"]
