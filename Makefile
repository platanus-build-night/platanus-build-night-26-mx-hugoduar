.PHONY: up down api worker migrate seed test

up:
	docker compose up -d

down:
	docker compose down

api:
	./manage.py runserver 8000

worker:
	celery -A noctua worker -l info

migrate:
	./manage.py migrate

seed:
	./manage.py seed_producers

test:
	pytest -x
