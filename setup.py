from setuptools import setup

setup(
    name='dm',
    version='0.0.1',
    packages=['utils', 'domain', 'domain.schemas', 'domain.entities', 'network', 'framework', 'framework.data',
              'framework.data.dao', 'framework.utils', 'framework.domain', 'framework.interfaces', 'use_cases',
              'repositories'],
    package_dir={'': 'dm'},
    url='',
    license='',
    author='joan.prat',
    author_email='joan.prat@dimensigon.com',
    description='', install_requires=['marshmallow', 'marshmallow_enum', 'returns', 'aiohttp', 'asynctest', 'attrdict',
                                      'PyYAML', 'requests', 'flask', 'click', 'psutil', 'flask_restful',
                                      'rsa', 'passlib', 'cryptography', 'coverage', 'tqdm',
                                      'flask-jwt-extended']
)
