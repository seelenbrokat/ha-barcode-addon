FROM ghcr.io/home-assistant/amd64-base-python:3.12

WORKDIR /app
COPY . /app

# Installiere Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere index.html nach /config/www
RUN mkdir -p /config/www && cp /app/index.html /config/www/index.html

EXPOSE 5000

# Starte mit run.sh, um Umgebungsvariablen zu setzen
CMD ["sh", "run.sh"]
