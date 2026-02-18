.PHONY: help build up down logs logs-d logs-t logs-s restart clean ps

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build all Docker images
	docker-compose build

up: ## Start all services in detached mode
	docker-compose up -d

down: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

logs: ## Follow logs from all services
	docker-compose logs -f

logs-d: ## Follow logs from discordbot
	docker-compose logs -f discordbot

logs-t: ## Follow logs from telegrambot
	docker-compose logs -f telegrambot

logs-s: ## Follow logs from steam
	docker-compose logs -f steam

ps: ## Show status of all services
	docker-compose ps

clean: ## Stop all services and remove images
	docker-compose down --rmi all

rebuild: ## Rebuild all services from scratch
	docker-compose build --no-cache
	docker-compose up -d
