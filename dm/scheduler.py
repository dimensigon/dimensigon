from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from tzlocal import get_localzone

import config as mod_config
from dm.defaults import flask_config
from dm.utils.helpers import from_obj

config = from_obj(mod_config.config_by_name[flask_config])

jobstores = {
    'default': SQLAlchemyJobStore(url=config['SQLALCHEMY_DATABASE_URI'])
}
executors = {
    'default': ProcessPoolExecutor(5),
}
job_defaults = {
    'coalesce': True,
    'max_instances': 4
}

scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults,
                                timezone=get_localzone())
