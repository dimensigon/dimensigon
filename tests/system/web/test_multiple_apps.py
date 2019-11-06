import copy
import datetime
from unittest import TestCase

from config import Config
from dm.web import create_app, catalog_manager
from threading import Lock

data1 = {
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

data2 = copy.deepcopy(data1)

data2.update({'ServerRepo': [
    dict(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='server1.localdomain', ip='127.0.0.1', port=80, birth=None,
         keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530100000'),
    dict(id='bbbbbbbb-1234-5678-1234-56781234bbb2', name='server2.localdomain', ip='127.0.0.1', port=81, birth=None,
         keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530100000'),
    dict(id='bbbbbbbb-1234-5678-1234-56781234bbb3', name='server3.localdomain', ip='127.0.0.1', port=80, birth=None,
         keep_alive=None, available=True, granules=[], route=[], alt_route=[], data_mark='20190101000530200000'),
],
    'CatalogRepo': [
        dict(entity='ActionTemplate', data_mark='20190101000530100000'),
        dict(entity='Step', data_mark='20190101000530100000'),
        dict(entity='Orchestration', data_mark='20190101000530100000'),
        dict(entity='Server', data_mark='20190101000530200000'),
    ]
})


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

from werkzeug.local import Local, LocalManager

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


class TestMultipleApplications(TestCase):

    def test_multiple_applications(self):

        app1 = create_app(Server1())
        app2 = create_app(Server2())

        client1 = app1.test_client()
        client2 = app2.test_client()

        r1 = client1.get('/api/v1.0/servers')
        r2 = client2.get('/api/v1.0/servers')

        route1 = list(filter(lambda d: d['id'] == 'bbbbbbbb-1234-5678-1234-56781234bbb3', r1.get_json()))[0]['route']
        route2 = list(filter(lambda d: d['id'] == 'bbbbbbbb-1234-5678-1234-56781234bbb3', r2.get_json()))[0]['route']
        self.assertListEqual(['bbbbbbbb-1234-5678-1234-56781234bbb2'], route1)
        self.assertListEqual([], route2)

        with app1.app_context():
            self.assertEqual(datetime.datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'),
                             catalog_manager.max_data_mark)

        with app2.app_context():
            self.assertEqual(datetime.datetime.strptime('20190101000530200000', '%Y%m%d%H%M%S%f'),
                             catalog_manager.max_data_mark)