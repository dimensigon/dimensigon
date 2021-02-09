from flask import url_for

from dimensigon import defaults
from dimensigon.domain.entities import bypass_datamark_update, ActionType, ActionTemplate
from dimensigon.web import db
from tests.base import TestDimensigonBase


class TestActionTemplate(TestDimensigonBase):

    def setUp(self) -> None:
        self.initials = dict(self.initials)
        self.initials.update(action_template=False)
        super().setUp()

    def fill_database(self):

        self.at1 = ActionTemplate(id="aaaaaaaa-1234-5678-1234-56781234aaa1", action_type=ActionType.SHELL,
                                  code="mkdir {dir}", last_modified_at=defaults.INITIAL_DATEMARK, name="mkdir",
                                  version=1)

        self.at2 = ActionTemplate(id="aaaaaaaa-1234-5678-1234-56781234aaa2",
                                  action_type=ActionType.SHELL,
                                  code="rmdir {dir}",
                                  last_modified_at=defaults.INITIAL_DATEMARK,
                                  expected_stdout='output',
                                  expected_stderr='err',
                                  expected_rc=0,
                                  name="rmdir",
                                  system_kwargs={'kwarg1': 1},
                                  pre_process='pre_process',
                                  post_process='post_process',
                                  version=1
                                  )

        with bypass_datamark_update():
            db.session.add_all([self.at1, self.at2])
            db.session.commit()

    def test_action_template_list(self):
        response = self.client.get(url_for('api_1_0.actiontemplatelist'), headers=self.auth.header)

        self.assertListEqual([self.at1.to_json(), self.at2.to_json()],
                             response.get_json())

    def test_action_template(self):
        response = self.client.get(
            url_for('api_1_0.actiontemplateresource', action_template_id="aaaaaaaa-1234-5678-1234-56781234aaa1"),
            headers=self.auth.header)

        self.assertDictEqual(
            self.at1.to_json(), response.get_json())
