import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    PROPAGATE_EXCEPTIONS = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATETIME_FORMAT = "%d/%m/%Y, %H:%M:%S"
    SSL_REDIRECT = False

    GIT_REPO = 'https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000'
    SSL_VERIFY = False
    SOFTWARE_DIR = os.path.join(basedir, 'software')
    AUTOUPGRADE = False

    @classmethod
    def init_app(cls, app):
        from flask.logging import default_handler
        app.logger.removeHandler(default_handler)
        os.makedirs(cls.SOFTWARE_DIR, exist_ok=True)


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'sqlite.db')
    AUTOUPGRADE = True

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        # email errors to the administrators
        # import logging
        # from logging.handlers import SMTPHandler
        # credentials = None
        # secure = None
        # if getattr(cls, 'MAIL_USERNAME', None) is not None:
        #     credentials = (cls.MAIL_USERNAME, cls.MAIL_PASSWORD)
        #     if getattr(cls, 'MAIL_USE_TLS', None):
        #         secure = ()
        # mail_handler = SMTPHandler(
        #     mailhost=(cls.MAIL_SERVER, cls.MAIL_PORT),
        #     fromaddr=cls.FLASKY_MAIL_SENDER,
        #     toaddrs=[cls.FLASKY_ADMIN],
        #     subject=cls.FLASKY_MAIL_SUBJECT_PREFIX + ' Application Error',
        #     credentials=credentials,
        #     secure=secure)
        # mail_handler.setLevel(logging.ERROR)
        # app.logger.addHandler(mail_handler)

        import logging
        from logging import StreamHandler
        stream_handler = StreamHandler()
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)


class GunicornConfig(ProductionConfig):
    AUTOUPGRADE = True

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        # from logging import FileHandler
        # file_handler = FileHandler('dimensigon.log')
        # file_handler.setLevel(logging.INFO)
        # app.logger.addHandler(file_handler)
        # fmt = logging.Formatter(
        #     "%(asctime)s [%(process)d] [%(module)s] [%(funcName)s] [%(name)s] [%(levelname)s] %(message)s")
        # file_handler.setFormatter(fmt)
        # for hdlr in app.logger.handlers:
        #     hdlr.setFormatter(fmt)


class UnixConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # log to syslog
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)


class TestingConfig(Config):
    TESTING = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    FLASK_RUN_PORT = 5000
    SERVER_HOST = '0.0.0.0'

    THREADS = 1
    WORKERS = 1


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    ENV = 'development'
    # SERVER_NAME = 'localhost.localdomain'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'dimensigon-dev.db')
    AUTOUPGRADE = False

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        import logging

        for h in app.logger.handlers:
            h.setLevel(logging.DEBUG)


config_by_name = dict(
    development=DevelopmentConfig(),
    test=TestingConfig(),
    production=ProductionConfig(),
    default=DevelopmentConfig(),
    unix=UnixConfig(),
    gunicorn=GunicornConfig()
)
