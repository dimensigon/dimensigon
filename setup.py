from setuptools import setup

setup(
    name='dm',
    version='0.0.1',
    # packages=['utils', 'domain', 'domain.schemas', 'domain.entities', 'network', 'use_cases'],
    # package_dir={'': 'dm'},
    url='',
    license='',
    author='joan.prat',
    author_email='joan.prat@dimensigon.com',
    description='',
    install_requires=['returns', 'aiohttp', 'asynctest', 'attrdict',
                      'requests', 'flask', 'click', 'psutil',
                      'flask_sqlalchemy', 'rsa', 'jsonschema', 'uwsgi'],
    entry_points={
        'console_scripts': [
            'dm = wsgi:main'
        ],
    }
)
