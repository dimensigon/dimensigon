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
        "aiohttp==3.7.3",
        "click==7.1.2",
        "coolname==1.1.0",
        "coverage==5.4",
        "cryptography==3.4.5",
        "dataclasses==0.8",
        "dill==0.3.3",
        "docopt==0.6.2",
        "gunicorn==20.0.4",
        "Flask-JWT-Extended==4.0.2",
        "Flask-RESTFul==0.3.8",
        "Flask-SQLAlchemy==2.4.4",
        "Flask==1.1.2",
        "jinja2==2.11.3",
        "jinja2schema==0.1.4",
        "jsonschema==3.2.0",
        "netifaces==0.10.9",
        "passlib==1.7.4",
        "prompt_toolkit==3.0.16",
        "Pygments==2.8.0",
        "python-dateutil==2.8.1",
        "PyYAML==5.4.1",
        "idna==2.10"
        "requests==2.25.1",
        "RestrictedPython==5.1",
        "rsa==4.7",
        "schema==0.7.4",
        "setuptools==53.0.0",
        "six==1.15.0",
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
