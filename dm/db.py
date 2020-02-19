from sqlalchemy import *
from sqlalchemy.orm import scoped_session, sessionmaker

from dm.defaults import flask_config
from dm.utils.helpers import from_obj


def make_engine(flask_config_):
    """This function used to collect data from Flask config
    """
    import config as mod_conf

    config = from_obj(mod_conf.config_by_name[flask_config_])

    if not (
            config.get('SQLALCHEMY_DATABASE_URI')
            or config.get('SQLALCHEMY_BINDS')
    ):
        raise RuntimeError('Either SQLALCHEMY_DATABASE_URI '
                           'or SQLALCHEMY_BINDS needs to be set.')

    config.setdefault('SQLALCHEMY_DATABASE_URI', None)
    # config.setdefault('SQLALCHEMY_BINDS', None)
    # config.setdefault('SQLALCHEMY_NATIVE_UNICODE', None)
    config.setdefault('SQLALCHEMY_ECHO', False)
    # config.setdefault('SQLALCHEMY_RECORD_QUERIES', None)
    # config.setdefault('SQLALCHEMY_POOL_SIZE', None)
    # config.setdefault('SQLALCHEMY_POOL_TIMEOUT', None)
    # config.setdefault('SQLALCHEMY_POOL_RECYCLE', None)
    # config.setdefault('SQLALCHEMY_MAX_OVERFLOW', None)
    # config.setdefault('SQLALCHEMY_COMMIT_ON_TEARDOWN', False)
    # config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    # config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {})

    return create_engine(config['SQLALCHEMY_DATABASE_URI'], echo=config.get('DEBUG', False))


engine = make_engine(flask_config)

Session = scoped_session(sessionmaker(bind=engine))

session = Session  # to mantain compatibility with Flask-SQLAlchemy


def create_all():
    from dm.model import Base
    Base.metadata.create_all(engine)


def drop_all():
    from dm.model import Base
    Base.metadata.drop_all(engine)
