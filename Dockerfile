FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY database.db database.db
COPY bot.py bot.py 
CMD ["python", "bot.py"]