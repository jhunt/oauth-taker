FROM alpine:3 as db
RUN apk add sqlite
WORKDIR /data
COPY schema.sql .
RUN sqlite3 /data/template.db <schema.sql

###

FROM python:3

# where is the SQLite3 database stored?
ENV OAUTH_TAKER_DATABASE=/data/oauth.db
VOLUME /data

# what host/port does Flask bind *inside* the container?
ENV BIND_HOST=0.0.0.0
ENV BIND_PORT=5000
EXPOSE 5000

# install Python dependencies
WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app
COPY app.py .

COPY --from=db /data/template.db /build/template.db
COPY entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
