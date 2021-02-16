THIS_FILE := $(lastword $(MAKEFILE_LIST))
.PHONY: help build up start down destroy stop restart logs logs-api ps login-timescale login-api db-shell
help:
	make -pRrq  -f $(THIS_FILE) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

build:
	docker-compose build dimensigon
up:
	docker-compose up dimensigon
start:
	docker-compose start dimensigon
down:
	docker-compose down dimensigon
destroy:
	docker-compose down -v dimensigon
logs:
	docker-compose logs --tail=100 -f dimensigon

test:
	find . -name '*.pyc' -exec rm -f {} \;
	python -m unittest discover -s tests -p 'test_*.py' -b

package:
	python setup.py sdist

clean:
	rm -rf build dist dimensigon.egg-info