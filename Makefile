COMPOSE = docker compose -f compose.yaml

.PHONY: help dev run down logs lint

help:
	@echo "Available targets:"
	@echo "  make dev   - Build & run the data service (Docker, hot-reload, foreground)"
	@echo "  make run   - Build & run the data service (Docker, detached)"
	@echo "  make down  - Stop the data service"
	@echo "  make logs  - Follow the data service logs"
	@echo "  make lint  - Run ruff inside the container"

## Lance la data en mode dev avec hot-reload (premier plan), sur http://localhost:8000
dev:
	$(COMPOSE) up --build -V

## Lance la data en arrière-plan (détaché), sur http://localhost:8000
run:
	$(COMPOSE) up --build -d

## Arrête la data
down:
	$(COMPOSE) down

## Affiche les logs de la data en temps réel
logs:
	$(COMPOSE) logs -f

## Lance le linter (ruff) dans le conteneur
lint:
	$(COMPOSE) run --rm data uv run ruff check .
