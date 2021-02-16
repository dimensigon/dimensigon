all:
	$(error please pick a target)

test:
#	find . -name '*.pyc' -exec rm -f {} \;
	python -m unittest discover -s tests -p 'test_*.py' -b

unit-test:
#	find . -name '*.pyc' -exec rm -f {} \;
	python -m unittest discover -s tests/unit -p 'test_*.py' -b

integration-test:
#	find . -name '*.pyc' -exec rm -f {} \;
	python -m unittest discover -s tests/integration -p 'test_*.py' -b

system-test:
#	find . -name '*.pyc' -exec rm -f {} \;
	python -m unittest discover -s tests/system -p 'test_*.py' -b