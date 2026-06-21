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
    JWT_ACCESS_TOKEN_EXPIRES = 28800  # 8 hours
    JWT_REFRESH_TOKEN_EXPIRES = 2592000  # 30 days
    JWT_TOKEN_LOCATION = ['headers', 'cookies']
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SAMESITE = 'Lax'

    # Container-native environment variable mappings
    DISCOVERY_DNS = os.environ.get('DM_DISCOVERY_DNS')
    AUTO_JOIN = os.environ.get('DM_AUTO_JOIN', 'true').lower() == 'true'
    NODE_NAME = os.environ.get('DM_NODE_NAME')
    GRACEFUL_SHUTDOWN_TIMEOUT = int(os.environ.get('DM_GRACEFUL_SHUTDOWN_TIMEOUT', '30'))

    # executor
    EXECUTOR_MAX_WORKERS = min(32, os.cpu_count() + 4)
    EXECUTOR_PROPAGATE_EXCEPTIONS = True

    AUTOUPGRADE = True
    PREFERRED_URL_SCHEME = 'https'  # scheme used to communicate with servers
    SECURIZER = True
    SECURIZER_PLAIN = True
    SECURIZER_MODE = 'auto'  # 'auto' (default), 'always', or 'never'
    SCHEDULER = True

    # AI chat assistant
    DM_AI_ENABLED = os.environ.get('DM_AI_ENABLED', 'false').lower() == 'true'

    # ------------------------------------------------------------------
    # Billing (Phase 2 — Stripe). ADDITIVE + ENV-GATED.
    #
    # All values default to None. When STRIPE_API_KEY is None the billing
    # blueprint still registers (it must never raise at import/startup) but
    # every billing endpoint returns HTTP 503 "billing not configured". No
    # Stripe client is initialised until a request actually needs it, so the
    # app behaves EXACTLY as before when these are unset.
    # ------------------------------------------------------------------
    STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    # Per-tier Stripe Price IDs (read from env — never hardcode live IDs).
    STRIPE_PRICE_COMMUNITY = os.environ.get('STRIPE_PRICE_COMMUNITY')
    STRIPE_PRICE_PRO = os.environ.get('STRIPE_PRICE_PRO')
    STRIPE_PRICE_ENTERPRISE = os.environ.get('STRIPE_PRICE_ENTERPRISE')
    # Optional redirect URLs for Stripe Checkout success/cancel pages.
    STRIPE_CHECKOUT_SUCCESS_URL = os.environ.get('STRIPE_CHECKOUT_SUCCESS_URL')
    STRIPE_CHECKOUT_CANCEL_URL = os.environ.get('STRIPE_CHECKOUT_CANCEL_URL')

    @classmethod
    def init_app(cls, app):
        pass


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = None

    @staticmethod
    def _require_secret_key(app):
        # CRITICAL: Fail fast in production if SECRET_KEY is not a strong value.
        # This runs at APP CREATION (init_app), never at module import — importing
        # web.config (e.g. by the dshell CLI or tests) must NOT raise just because
        # this process has no DM_SECRET_KEY. Only a real production app start enforces it.
        secret = os.environ.get('DM_SECRET_KEY')
        if not secret or secret == 'hard to guess string':
            raise ValueError(
                'FATAL: DM_SECRET_KEY must be set to a strong random value in production.\n'
                'Generate with: python -c "import secrets; print(secrets.token_urlsafe(48))"\n'
                'Never use the placeholder "hard to guess string".\n'
                'Set DM_SECRET_KEY environment variable before starting the application.'
            )
        app.config['SECRET_KEY'] = secret

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        cls._require_secret_key(app)

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
    """Gunicorn production config - inherits SECRET_KEY validation from ProductionConfig"""

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        cls._require_secret_key(app)
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
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_CSRF_PROTECT = False

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
