IMAGE ?= filefrog/oauth-taker
TAG   ?= latest

build:
	docker build -t $(IMAGE):$(TAG) .
push: build
	docker push $(IMAGE):$(TAG)

dev:
	IMAGE=oathdev make build
	@docker stop oathdev 2>/dev/null || true
	@docker rm   oathdev 2>/dev/null || true
	docker run -d --name oathdev \
	           -v ./_dev/data:/data \
	           -v ./app.py:/app/app.py:ro \
	           -p 5009:5000 \
	           oathdev
	@echo "insert into api_keys (shared_key, enabled_after, disabled_after) values ('a-test-dev-apikey', current_timestamp, '2030-12-31 23:59:59');" | sudo sqlite3 _dev/data/oauth.db
	@echo "running at http://localhost:5009 ..."
