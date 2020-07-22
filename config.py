import logging
import os

import dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

dotenv.load_dotenv(dotenv.find_dotenv())


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    PROPAGATE_EXCEPTIONS = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    DATETIME_FORMAT = "%d/%m/%Y, %H:%M:%S"
    SSL_REDIRECT = False
    SSL_VERIFY = False

    GIT_REPO = os.environ.get('DM_GIT_REPO') or 'https://codebase.knowtrade.ch:3000'
    SOFTWARE_REPO = os.path.abspath(os.path.expanduser(
        os.environ.get('DM_SOFTWARE_REPO', os.path.join("~", 'software'))))
    LOG_REPO = os.path.abspath(os.path.expanduser(
        os.environ.get('DM_LOG_REPO', os.path.join("~", 'log'))))
    AUTOUPGRADE = True
    PREFERRED_URL_SCHEME = 'https'  # scheme used to communicate with servers
    SECURIZER = True
    SECURIZER_PLAIN = True
    SCHEDULER = True

    @classmethod
    def init_app(cls, app):
        os.makedirs(cls.SOFTWARE_REPO, exist_ok=True)
        os.makedirs(os.path.join(cls.SOFTWARE_REPO, 'dimensigon'), exist_ok=True)
        os.makedirs(cls.LOG_REPO, exist_ok=True)


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'sqlite.db')
    PROPAGATE_EXCEPTIONS = False

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
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    AUTOUPGRADE = False
    SERVER_NAME = 'test'
    PREFERRED_URL_SCHEME = 'http'
    SECURIZER = False
    DEBUG = False

    @classmethod
    def init_app(cls, app):
        super().init_app(app)
        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        for logger in loggers:
            logger.handlers = []
        logging.root.handlers = []


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
