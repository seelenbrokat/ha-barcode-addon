FROM python:3.11-slim

WORKDIR /app
COPY . /app

# Installiere Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere index.html nach /config/www
RUN mkdir -p /config/www && cp /app/index.html /config/www/index.html

EXPOSE 5000

# Starte das Flask-Backend
CMD ["python3", "webapp.py"]
