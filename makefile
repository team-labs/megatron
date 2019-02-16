# makefile

start-dev:
	docker-compose up

test:
	cp app/django-variables.env.local app/.env
	cd app && pipenv run pytest

