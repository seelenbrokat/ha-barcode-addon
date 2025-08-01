FROM python:3.11-slim

WORKDIR /app
COPY . /app

# Installiere spezifische Versionen der Abhängigkeiten
RUN pip install --no-cache-dir \
    Flask==3.0.0 \
    PyMySQL==1.1.1 \
    flask_cors==4.0.1

# Kopiere index.html nach /config/www
RUN mkdir -p /config/www && cp /app/index.html /config/www/index.html

EXPOSE 5000

# Starte mit run.sh, um Umgebungsvariablen zu setzen
CMD ["sh", "run.sh"]
