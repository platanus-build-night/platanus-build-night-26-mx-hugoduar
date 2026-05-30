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

.PHONY: reset-demo
reset-demo:
	cd ../noctua-demo-app && \
	  (gh pr list --state all --json number --jq '.[].number' | xargs -n1 -I{} gh pr close {} 2>/dev/null || true) && \
	  git fetch origin && git reset --hard origin/main && \
	  (git branch | grep noctua/ | xargs -n1 -I{} git branch -D {} 2>/dev/null || true)
