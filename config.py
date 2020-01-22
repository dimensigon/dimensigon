import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    PROPAGATE_EXCEPTIONS = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATETIME_FORMAT = "%m/%d/%Y, %H:%M:%S"


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data.sqlite')


class TestingConfig(Config):
    TESTING = True
    SERVER_NAME = 'server1'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    ENV = 'development'
    SERVER_NAME = 'localhost.localdomain'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'dimensigon-dev.db')


config_by_name = dict(
    dev=DevelopmentConfig(),
    test=TestingConfig(),
    prod=ProductionConfig()
)
