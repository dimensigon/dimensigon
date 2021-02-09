import datetime as dt
from unittest.mock import patch

from flask import url_for

from dimensigon import defaults
from dimensigon.domain.entities import Server, ActionTemplate, ActionType
from dimensigon.web import db
from tests.base import TestDimensigonBase


class TestCatalog(TestDimensigonBase):

    @patch('dimensigon.web.api_1_0.urls.use_cases.get_distributed_entities')
    @patch('dimensigon.domain.entities.get_now')
    def test_catalog(self, mock_now, mock_get):
        mock_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        mock_get.return_value = [('ActionTemplate', ActionTemplate)]

        at1 = ActionTemplate(name='ActionTest1', version=1, action_type=ActionType.ORCHESTRATION, code='')
        db.session.add(at1)
        db.session.commit()

        resp = self.client.get(
            url_for('api_1_0.catalog',
                    data_mark=dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc).strftime(defaults.DATEMARK_FORMAT)),
            headers=self.auth.header)

        self.assertDictEqual({'ActionTemplate': [at1.to_json()]},
                             resp.get_json())

        mock_now.return_value = dt.datetime(2019, 4, 2, 1, tzinfo=dt.timezone.utc)
        at2 = ActionTemplate(name='ActionTest2', version=1, action_type=ActionType.ORCHESTRATION, code='')
        db.session.add(at2)
        db.session.commit()

        resp = self.client.get(
            url_for('api_1_0.catalog',
                    data_mark=dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc).strftime(defaults.DATEMARK_FORMAT)),
            headers=self.auth.header)

        self.assertDictEqual({'ActionTemplate': [at2.to_json()]},
                             resp.get_json())
