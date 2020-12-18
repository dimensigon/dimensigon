import logging
import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    CONFIG_FOLDER = None
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.environ.get('DM_SECRET_KEY') or 'hard to guess string'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATETIME_FORMAT = "%d/%m/%Y, %H:%M:%S"
    SSL_REDIRECT = False
    SSL_VERIFY = False
    PROPAGATE_EXCEPTIONS = False

    JWT_DECODE_LEEWAY = 15

    # executor
    EXECUTOR_MAX_WORKERS = min(32, os.cpu_count() + 4)
    EXECUTOR_PROPAGATE_EXCEPTIONS = True

    AUTOUPGRADE = True
    PREFERRED_URL_SCHEME = 'https'  # scheme used to communicate with servers
    SECURIZER = True
    SECURIZER_PLAIN = True
    SCHEDULER = True

    @classmethod
    def init_app(cls, app):
        pass


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = None

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

        # import logging
        # from logging import StreamHandler
        # stream_handler = StreamHandler()
        # stream_handler.setLevel(logging.INFO)
        # app.logger.addHandler(stream_handler)


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
    SQLALCHEMY_DATABASE_URI = os.environ.get('DM_DEV_DATABASE_URL') or \
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
    default=ProductionConfig(),
    unix=UnixConfig(),
    gunicorn=GunicornConfig()
)
