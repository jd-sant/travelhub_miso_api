.PHONY: help docker-up docker-down docker-build docker-logs clean users-test users-build users-logs security-test security-build security-logs reservations-test reservations-build reservations-logs

help:
	@echo "=== TravelHub Monorepo ==="
	@echo ""
	@echo "Global:"
	@echo "  make docker-up      - Start all services"
	@echo "  make docker-down    - Stop all services"
	@echo "  make docker-build   - Build all images"
	@echo "  make docker-logs    - Tail all logs"
	@echo "  make clean          - Remove __pycache__ files"
	@echo ""
	@echo "Users service:"
	@echo "  make users-test     - Run users tests"
	@echo "  make users-build    - Build users image"
	@echo "  make users-logs     - Tail users logs"
	@echo ""
	@echo "Security service:"
	@echo "  make security-test  - Run security tests"
	@echo "  make security-build - Build security image"
	@echo "  make security-logs  - Tail security logs"
	@echo ""
	@echo "Reservations service:"
	@echo "  make reservations-test  - Run reservations tests"
	@echo "  make reservations-build - Build reservations image"
	@echo "  make reservations-logs  - Tail reservations logs"

# Global commands
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Users service
users-test:
	cd services/users && PYTHONPATH=src pytest tests/ -v

users-build:
	docker compose build users

users-logs:
	docker compose logs -f users

# Security service
security-test:
	cd services/security && PYTHONPATH=src pytest tests/ -v

security-build:
	docker compose build security

security-logs:
	docker compose logs -f security

# Reservations service
reservations-test:
	cd services/reservations && PYTHONPATH=src pytest tests/ -v

reservations-build:
	docker compose build reservations

reservations-logs:
	docker compose logs -f reservations
