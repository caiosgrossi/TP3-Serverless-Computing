# Lightweight image for Streamlit dashboard
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

EXPOSE 50105

# Disable file watcher to avoid inotify limits in containers.
ENV STREAMLIT_SERVER_FILE_WATCHER_TYPE=none

CMD ["streamlit", "run", "app.py", "--server.port", "50105", "--server.address", "0.0.0.0"]
