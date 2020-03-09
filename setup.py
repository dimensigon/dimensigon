
from setuptools import setup, find_packages

import dm

setup(
    name='dm',
    version=dm.__version__,
    packages=find_packages(),
    url='',
    license=dm.__license__,
    author=dm.__author__,
    author_email=dm.__email__,
    description='',
    install_requires=['returns', 'aiohttp', 'asynctest', 'attrdict',
                      'requests', 'flask', 'click', 'psutil',
                      'flask_sqlalchemy', 'rsa', 'jsonschema', 'uwsgi'],
    scripts=['dimensigon.py', 'elevator.py'],
)
