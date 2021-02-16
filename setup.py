import re

from setuptools import setup, find_packages

INIT_FILE = 'dimensigon/__init__.py'

with open("README.md", "r") as fh:
    long_description = fh.read()


def find_version():
    with open(INIT_FILE) as fp:
        for line in fp:
            # __version__ = '0.1.0'
            match = re.search(r"__version__\s*=\s*(['\"])([^\1]+)\1", line)
            if match:
                return match.group(1)
    assert False, 'cannot find version'


def find_author_email():
    with open(INIT_FILE) as fp:
        m_author, m_email = None, None
        for line in fp:
            if not m_author:
                m_author = re.search(r"__author__\s*=\s*(['\"])([^\1]*)\1", line)
            if not m_email:
                m_email = re.search(r"__email__\s*=\s*(['\"])([^\1]*)\1", line)
            if m_author and m_email:
                return m_author.group(1), m_email.group(1)
    assert False, 'cannot find author or email'


def find_licence():
    with open(INIT_FILE) as fp:
        for line in fp:
            match = re.search(r"__license__\s*=\s*(['\"])([^\1]*)\1", line)
            if match:
                return match.group(1)
    assert False, 'cannot find license'


def required_packages():
    with open('requirements.txt') as fp:
        return [line.strip() for line in fp if line.strip()]


author, email = find_author_email()
setup(
    name='dimensigon',
    version=find_version(),
    package_dir={"": "."},
    packages=find_packages(where=".", exclude=["contrib", "docs", "tests*", "tasks"]),
    url='https://github.com/dimensigon/dimensigon',
    license=find_licence(),
    author=author,
    author_email=email,
    description="Distributed Management and orchestration through RESTful, Mesh Networking and with a flair of IoT.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    test_suite="tests",
    install_requires=required_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX",
    ],
    entry_points={'console_scripts': ["dshell=dimensigon.dshell.batch.dshell:main",
                                      "dimensigon=dimensigon.__main__:main"]},
    python_requires='>=3.6',
)
