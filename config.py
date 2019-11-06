import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    PROPAGATE_EXCEPTIONS = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False



class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data.sqlite')

data = {
    'ActionTemplateRepo': [
        dict(id='aaaaaaaa-1234-5678-1234-56781234aaa1', name='mkdir', version=1, action_type='NATIVE',
             code='mkdir {dir}', parameters={}, expected_output=None, expected_rc=None,
             system_kwargs={}, data_mark='20190101000530100000'),
        dict(id='aaaaaaaa-1234-5678-1234-56781234aaa2', name='rmdir', version=1, action_type='NATIVE',
             code='rmdir {dir}', parameters={}, expected_output=None, expected_rc=None,
             system_kwargs={}, data_mark='20190101000530100000')
    ],
    'StepRepo': [
        dict(id='eeeeeeee-1234-5678-1234-56781234eee1', undo=False, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa1',
             step_expected_output=None, step_expected_rc=0, step_parameters={'dir': 'folder'}, step_system_kwargs=None,
             data_mark='20190101000530100000'),
        dict(id='eeeeeeee-1234-5678-1234-56781234eee2', undo=True, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa2',
             step_expected_output=None, step_expected_rc=0, step_parameters={'dir': 'folder'},
             step_system_kwargs=None, data_mark='20190101000530100000')
    ],
    'OrchestrationRepo': [
        dict(id='cccccccc-1234-5678-1234-56781234ccc1', name='create folder', version=1,
             description='Creates a folder on the specified location',
             steps=['eeeeeeee-1234-5678-1234-56781234eee1',
                    'eeeeeeee-1234-5678-1234-56781234eee2'],
             dependencies={'eeeeeeee-1234-5678-1234-56781234eee1': ['eeeeeeee-1234-5678-1234-56781234eee2'],
                           'eeeeeeee-1234-5678-1234-56781234eee2': []},
             data_mark='20190101000530100000')
    ],
    'ServerRepo': [
        dict(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='localhost.localdomain', ip='127.0.0.1', port=80, birth=None,
             keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530100000'),
        dict(id='bbbbbbbb-1234-5678-1234-56781234bbb2', name='server1.localdomain', ip='127.0.0.1', port=80, birth=None,
                     keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530100000')
    ],
    'CatalogRepo': [
        dict(entity='ActionTemplate', data_mark='20190101000530100000'),
        dict(entity='Step', data_mark='20190101000530100000'),
        dict(entity='Orchestration', data_mark='20190101000530100000'),
        dict(entity='Server', data_mark='20190101000530100000'),
    ]
}


class TestingConfig(Config):
    TESTING = True
    SERVER_NAME = 'localhost.localdomain'
    REPOSITORY = 'memory'
    DM_DATABASE_CONTENT = data


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    ENV = 'development'
    SERVER_NAME = 'localhost.localdomain'
    REPOSITORY = 'memory'
    DM_DATABASE_CONTENT = data
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
    #                           'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')
    SQLALCHEMY_DATABASE_URI = None



config_by_name = dict(
    dev=DevelopmentConfig(),
    test=TestingConfig(),
    prod=ProductionConfig()
)
