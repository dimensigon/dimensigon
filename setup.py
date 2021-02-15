from setuptools import setup, find_packages

import dimensigon as dm

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='dimensigon',
    version=dm.__version__,
    package_dir={"": "."},
    packages=find_packages(where=".", exclude=["contrib", "docs", "tests*", "tasks"]),
    url='https://github.com/dimensigon/dimensigon',
    license=dm.__license__,
    author=dm.__author__,
    author_email=dm.__email__,
    description="Distributed Management and orchestration through RESTful, Mesh Networking and with a flair of IoT.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "aiohttp",
        "click",
        "coolname",
        "coverage",
        "cryptography",
        "dataclasses",
        "dill",
        "docopt",
        "gunicorn",
        "Flask-JWT-Extended>=4.0.0",
        "Flask-RESTFul",
        "Flask-SQLAlchemy",
        "Flask",
        "jinja2",
        "jinja2schema",
        "jsonschema",
        "netifaces",
        "passlib",
        "prompt_toolkit",
        "Pygments",
        "python-dateutil",
        "PyYAML",
        "requests",
        "RestrictedPython",
        "rsa",
        "schema",
        "setuptools",
        "six",
    ],
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX",
    ],
    entry_points={'console_scripts': ["dshell=dimensigon.dshell.batch.dshell:main",
                                      "dimensigon=dimensigon.__main__:main"]},
    python_requires='>=3.6',
)
