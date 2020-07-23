from setuptools import setup, find_packages

import dm

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='dimensigon',
    version=dm.__version__,
    packages=find_packages(),
    url='https://github.com/dimensigon/dimensigon',
    license=dm.__license__,
    author=dm.__author__,
    author_email=dm.__email__,
    description="Dimensigon (DM) is a Distributed Management and Automation RESTful framework to make easier heterogeneous/polyglot orchestrations in a Hybrid Multi-Cloud environment.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "beautifulsoup4",
        "PyYAML",
        "six",
        "flask",
        "flask-JWT-Extended",
        "flask-Migrate",
        "flask-RESTFul",
        "flask-SQLAlchemy",
        "requests",
        "rsa",
        "coverage",
        "jsonschema",
        "aiohttp",
        "dataclasses",
        "cryptography",
        "psutil",
        "python-dotenv",
        "netifaces",
        "apscheduler",
        "passlib",
        "jinja2",
        "SQLAlchemy",
        "Werkzeug",
        "jinja2schema",
        "RestrictedPython",
        "setuptools",
        "click",
        "pygments"
    ],
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX",
    ],
    python_requires='>=3.6',
    entry_points = {'console_scripts': ['dshell=dm.dshell.batch.dshell:main']},
)
