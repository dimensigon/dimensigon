THIS_FILE := $(lastword $(MAKEFILE_LIST))
.PHONY: help build docker-test test package upload clean
help:
	make -pRrq  -f $(THIS_FILE) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

build:
	docker-compose build dimensigon

docker-test:
	docker-compose up --build dimensigon

test:
	find . -name '*.pyc' -exec rm -f {} \;
	python -m unittest discover -s tests -p 'test_*.py' -b

package:
	python setup.py sdist bdist_wheel

upload:
	python -m twine upload ./dist/*

clean:
	rm -rf build dist dimensigon.egg-info

clean_upload: package upload clean