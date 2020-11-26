from unittest import mock

from dimensigon import defaults
from dimensigon.domain.entities import Vault
from dimensigon.domain.entities.user import ROOT, User, JOIN
from dimensigon.utils.helpers import get_now
from dimensigon.web import db
from tests.base import TestDimensigonBase


class TestVault(TestDimensigonBase):

    @mock.patch('dimensigon.domain.entities.get_now')
    def test_to_json(self, mock_get_now):
        mock_get_now.return_value = get_now()
        v = Vault(user=User.get_by_name('root'), name='foo', value="foo_value")
        db.session.add(v)

        self.assertEqual(dict(user_id=ROOT, name='foo', value="foo_value"), v.to_json(no_delete=True))
        self.assertEqual(dict(user=dict(id=ROOT, name='root'), name='foo', value="foo_value"),
                         v.to_json(human=True, no_delete=True))
        db.session.commit()
        db.session.remove()
        del v

        v = Vault.query.get((ROOT, 'global', 'foo'))
        self.assertEqual(dict(user_id=ROOT, name='foo', scope='global', value="foo_value",
                              last_modified_at=mock_get_now.return_value.strftime(defaults.DATEMARK_FORMAT)),
                         v.to_json(no_delete=True))

    def test_from_json(self):
        v = Vault.from_json(dict(user_id=ROOT, name='foo', value="foo_value"))

        self.assertEqual(ROOT, v.user.id)
        self.assertEqual('foo', v.name)
        self.assertEqual('foo_value', v.value)

        self.assertNotIn(v, db.session)

        db.session.add(v)
        db.session.commit()
        self.assertEqual('global', v.scope)

        db.session.remove()
        v = Vault.from_json(dict(user_id=ROOT, name='foo', value="new_value"))

        self.assertEqual('new_value', v.value)

        self.assertIn(v, db.session)

    def test_get_variables_from(self):
        v1 = Vault(user_id=ROOT, name='foo', value=1)
        v2 = Vault(user_id=JOIN, name='foo', value=2)

        db.session.add_all([v1, v2])
        self.assertDictEqual(dict(foo=1), Vault.get_variables_from(ROOT))
        self.assertDictEqual(dict(foo=1), Vault.get_variables_from(User.get_by_name('root')))
