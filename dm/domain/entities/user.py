import typing as t
from datetime import datetime

from passlib.hash import sha256_crypt

from dm import defaults
from dm.domain.entities.base import UUIDistributedEntityMixin
from dm.utils.typos import ScalarListType
from dm.web import db


class User(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_user'

    user = db.Column(db.String(30), nullable=False)
    _password = db.Column('password', db.String(256))
    email = db.Column(db.String)
    created_at = db.Column(db.Date)
    active = db.Column('is_active', db.Boolean(), nullable=False)
    groups = db.Column(ScalarListType(str))

    __table_args__ = (db.UniqueConstraint('user', name='D_user_uq01'),)

    def __init__(self, user, password=None, email=None, created_at=None, active=True, groups: t.Union[str, t.List[str]] = None,
                 **kwargs):

        UUIDistributedEntityMixin.__init__(self, **kwargs)
        self.user = user
        self._password = password or kwargs.get('_password', None)
        self.email = email
        self.created_at = created_at or datetime.now()
        self.active = active
        if isinstance(groups, str):
            self.groups = groups.split(':')
        else:
            self.groups = groups or []

    @classmethod
    def get_by_user(cls, user):
        return db.session.query(cls).filter_by(user=user).one_or_none()

    @classmethod
    def get_by_group(cls, group):
        return [g for g in db.session.query(cls).all() if group in g.groups]

    def _hash_password(self, password):
        if not self._password:
            self._password = sha256_crypt.encrypt(password)

    def verify_password(self, password) -> bool:
        return sha256_crypt.verify(password, self._password)

    def set_password(self, password):
        self._password = None
        self._hash_password(password)

    def to_json(self, password=False) -> dict:
        data = super().to_json()
        data.update(user=self.user, email=self.email, created_at=self.created_at.strftime(defaults.DATETIME_FORMAT),
                    active=self.active, groups=','.join(self.groups))
        if password:
            data.update(_password=self._password)
        return data

    @classmethod
    def from_json(cls, kwargs):
        kwargs = dict(kwargs)
        if 'created_at' in kwargs:
            kwargs['created_at'] = datetime.strptime(kwargs.get('created_at'), defaults.DATETIME_FORMAT)
        if 'groups' in kwargs:
            kwargs['groups'] = kwargs['groups'].split(':')
        return super().from_json(kwargs)

    @classmethod
    def set_initial(cls):
        root = cls.get_by_user('root')
        if not root:
            root = User(user='root', groups=['administrator'])
            root.hash_password('12345678')
            db.session.add(root)
        ops = cls.get_by_user('ops')
        if not ops:
            ops = User(user='ops', groups=['operator', 'deployer'])
            db.session.add(ops)
        reporter = cls.get_by_user('reporter')
        if not reporter:
            reporter = User(user='reporter', groups=['readonly'])
            db.session.add(reporter)
