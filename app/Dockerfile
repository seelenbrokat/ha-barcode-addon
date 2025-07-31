FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install flask pymysql

EXPOSE 5000

CMD ["python", "webapp.py"]
