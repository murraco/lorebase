.PHONY: lint format test migrate makemigrations run shell

lint:
	uv run ruff check .
	uv run mypy .

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

migrate:
	uv run python manage.py migrate

makemigrations:
	uv run python manage.py makemigrations

run:
	uv run python manage.py runserver

shell:
	uv run python manage.py shell
