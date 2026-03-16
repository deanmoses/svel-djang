.PHONY: bootstrap dev test lint quality agent-docs api-gen ingest superuser explore pinbase-export

bootstrap:
	./scripts/bootstrap

dev:
	./scripts/dev

test:
	./scripts/test

lint:
	./scripts/lint

quality: lint api-gen
	cd frontend && pnpm check
	@echo "All quality checks passed!"

agent-docs:
	python3 scripts/build_agent_docs.py

api-gen:
	cd backend && uv run python manage.py export_openapi_schema
	cd frontend && pnpm api:gen

ingest:
	cd backend && uv run python manage.py ingest_all --write

superuser:
	cd backend && DJANGO_SUPERUSER_EMAIL="" uv run python manage.py createsuperuser --noinput

pinbase-export:
	python scripts/export_pinbase_json.py

explore: pinbase-export
	rm -f data/explore/explore.duckdb
	duckdb data/explore/explore.duckdb < data/explore/explore.sql
