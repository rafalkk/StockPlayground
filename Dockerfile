FROM python:3

WORKDIR /APP

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY gunicorn.conf.py ./
COPY helpers.py ./
COPY static/ ./static/
COPY templates/ ./templates/

EXPOSE 5000


CMD ["gunicorn", "app:app"]