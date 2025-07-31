FROM python:3.11-slim

WORKDIR /app
COPY . /app

# Besser: dependencies aus requirements.txt, damit du flexibler bist
# RUN pip install flask pymysql
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Starte das Flask-Backend (python3 ist Standard, falls du Python 3.11 nimmst)
CMD ["python3", "webapp.py"]
