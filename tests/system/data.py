from dimensigon.web.config import Config

data1 = {
    'ActionTemplateRepo': [
        dict(id='aaaaaaaa-1234-5678-1234-56781234aaa1', name='mkdir', version=1, action_type='SHELL',
             code='mkdir {dir}', expected_output=None, expected_rc=None,
             system_kwargs={}, data_mark='20190101000530100000'),
        dict(id='aaaaaaaa-1234-5678-1234-56781234aaa2', name='rmdir', version=1, action_type='SHELL',
             code='rmdir {dir}', expected_output=None, expected_rc=None,
             system_kwargs={}, data_mark='20190101000530100000')
    ],
    'StepRepo': [
        dict(id='eeeeeeee-1234-5678-1234-56781234eee1', undo=False, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa1',
             step_expected_output=None, step_expected_rc=0, step_system_kwargs=None,
             data_mark='20190101000530100000'),
        dict(id='eeeeeeee-1234-5678-1234-56781234eee2', undo=True, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa2',
             step_expected_output=None, step_expected_rc=0,              step_system_kwargs=None, data_mark='20190101000530100000')
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
        dict(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='server1.localdomain', ip='127.0.0.1', port=80, birth=None,
             keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530100000'),
        dict(id='bbbbbbbb-1234-5678-1234-56781234bbb2', name='server2.localdomain', ip='127.0.0.1', port=81, birth=None,
             keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530100000'),
        dict(id='bbbbbbbb-1234-5678-1234-56781234bbb3', name='server3.localdomain', ip='127.0.0.1', port=80, birth=None,
             keep_alive=None, available=True, granules=[], route=['bbbbbbbb-1234-5678-1234-56781234bbb2'],
             alt_route=[], data_mark='20190101000530100000'),
    ],
    'CatalogRepo': [
        dict(entity='ActionTemplate', data_mark='20190101000530100000'),
        dict(entity='Step', data_mark='20190101000530100000'),
        dict(entity='Orchestration', data_mark='20190101000530100000'),
        dict(entity='Server', data_mark='20190101000530100000'),
    ]
}

data2 = {'ActionTemplateRepo': [
    dict(id='aaaaaaaa-1234-5678-1234-56781234aaa1', name='mkdir', version=1, action_type='SHELL',
         code='mkdir {dir}', xpected_output=None, expected_rc=None,
         system_kwargs={}, data_mark='20190101000532100000'),
    dict(id='aaaaaaaa-1234-5678-1234-56781234aaa2', name='rmdir', version=1, action_type='SHELL',
         code='rmdir {dir}', expected_output=None, expected_rc=None,
         system_kwargs={}, data_mark='20190101000530100000'),
    dict(id='aaaaaaaa-1234-5678-1234-56781234aaa3', name='install mysql', version=1, action_type='SHELL',
         code='yum install mysql', expected_output=None, expected_rc=None,
         system_kwargs={}, data_mark='20190101000531100000'),
    dict(id='aaaaaaaa-1234-5678-1234-56781234aaa4', name='start mysql', version=1, action_type='SHELL',
         code='service start mysql', expected_output=None, expected_rc=None,
         system_kwargs={}, data_mark='20190101000531100000')
],
    'StepRepo': [
        dict(id='eeeeeeee-1234-5678-1234-56781234eee1', undo=False, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa1',
             step_expected_output=None, step_expected_rc=0, step_system_kwargs=None,
             data_mark='20190101000530100000'),
        dict(id='eeeeeeee-1234-5678-1234-56781234eee2', undo=True, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa2',
             step_expected_output=None, step_expected_rc=0,              step_system_kwargs=None, data_mark='20190101000530100000'),
        dict(id='eeeeeeee-1234-5678-1234-56781234eee3', undo=False, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa3',
             step_expected_output=None, step_expected_rc=0, step_parameters={}, step_system_kwargs=None,
             data_mark='20190101000532100000'),
        dict(id='eeeeeeee-1234-5678-1234-56781234eee4', undo=True, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa4',
             step_expected_output=None, step_expected_rc=0, step_parameters={}, step_system_kwargs=None,
             data_mark='20190101000533100000')
    ],
    'OrchestrationRepo': [
        dict(id='cccccccc-1234-5678-1234-56781234ccc1', name='create folder', version=1,
             description='Creates a folder on the specified location',
             steps=['eeeeeeee-1234-5678-1234-56781234eee1',
                    'eeeeeeee-1234-5678-1234-56781234eee2'],
             dependencies={'eeeeeeee-1234-5678-1234-56781234eee1': ['eeeeeeee-1234-5678-1234-56781234eee2'],
                           'eeeeeeee-1234-5678-1234-56781234eee2': []},
             data_mark='20190101000530100000'),
        dict(id='cccccccc-1234-5678-1234-56781234ccc2', name='create folder', version=1,
             description='Creates a folder on the specified location',
             steps=['eeeeeeee-1234-5678-1234-56781234eee3',
                    'eeeeeeee-1234-5678-1234-56781234eee4'],
             dependencies={'eeeeeeee-1234-5678-1234-56781234eee3': ['eeeeeeee-1234-5678-1234-56781234eee4'],
                           'eeeeeeee-1234-5678-1234-56781234eee4': []},
             data_mark='20190101000534100000')
    ],
    'ServerRepo': [
        dict(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='server1.localdomain', ip='127.0.0.1', port=80, birth=None,
             keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530100000'),
        dict(id='bbbbbbbb-1234-5678-1234-56781234bbb2', name='server2.localdomain', ip='127.0.0.1', port=81, birth=None,
             keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530100000'),
        dict(id='bbbbbbbb-1234-5678-1234-56781234bbb3', name='server3.localdomain', ip='127.0.0.1', port=80, birth=None,
             keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530200000'),
    ],
    'CatalogRepo': [
        dict(entity='ActionTemplate', data_mark='20190101000532100000'),
        dict(entity='Step', data_mark='20190101000533100000'),
        dict(entity='Orchestration', data_mark='20190101000534100000'),
        dict(entity='Server', data_mark='20190101000530200000'),
    ]
}

delta = {'ActionTemplateRepo': [
    dict(id='aaaaaaaa-1234-5678-1234-56781234aaa1', name='mkdir', version=1, action_type='SHELL',
         code='mkdir {dir}', parameters={}, expected_output=None, expected_rc=None,
         system_kwargs={}, data_mark='20190101000532100000'),
    dict(id='aaaaaaaa-1234-5678-1234-56781234aaa3', name='install mysql', version=1, action_type='SHELL',
         code='yum install mysql', parameters={}, expected_output=None, expected_rc=None,
         system_kwargs={}, data_mark='20190101000531100000'),
    dict(id='aaaaaaaa-1234-5678-1234-56781234aaa4', name='start mysql', version=1, action_type='SHELL',
         code='service start mysql', parameters={}, expected_output=None, expected_rc=None,
         system_kwargs={}, data_mark='20190101000531100000')
],
    'StepRepo': [
        dict(id='eeeeeeee-1234-5678-1234-56781234eee3', undo=False, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa3',
             step_expected_output=None, step_expected_rc=0, step_parameters={}, step_system_kwargs=None,
             data_mark='20190101000532100000'),
        dict(id='eeeeeeee-1234-5678-1234-56781234eee4', undo=True, stop_on_error=True,
             action_template='aaaaaaaa-1234-5678-1234-56781234aaa4',
             step_expected_output=None, step_expected_rc=0, step_parameters={}, step_system_kwargs=None,
             data_mark='20190101000533100000')
    ],
    'OrchestrationRepo': [
        dict(id='cccccccc-1234-5678-1234-56781234ccc2', name='create folder', version=1,
             description='Creates a folder on the specified location',
             steps=['eeeeeeee-1234-5678-1234-56781234eee3',
                    'eeeeeeee-1234-5678-1234-56781234eee4'],
             dependencies={'eeeeeeee-1234-5678-1234-56781234eee3': ['eeeeeeee-1234-5678-1234-56781234eee4'],
                           'eeeeeeee-1234-5678-1234-56781234eee4': []},
             data_mark='20190101000534100000')
    ],
    'ServerRepo': [
        dict(id='bbbbbbbb-1234-5678-1234-56781234bbb3', name='server3.localdomain', ip='127.0.0.1', port=80, birth=None,
             keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530200000'),
    ]
}


class Server1(Config):
    DEVELOPMENT = True
    DEBUG = True
    ENV = 'development'
    SERVER_NAME = 'server1.localdomain'
    REPOSITORY = 'memory'
    DM_DATABASE_CONTENT = data1
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
    #                           'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')
    SQLALCHEMY_DATABASE_URI = None


class Server2(Config):
    DEVELOPMENT = True
    DEBUG = True
    ENV = 'development'
    SERVER_NAME = 'server2.localdomain'
    REPOSITORY = 'memory'
    DM_DATABASE_CONTENT = data2
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
    #                           'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')
    SQLALCHEMY_DATABASE_URI = None
