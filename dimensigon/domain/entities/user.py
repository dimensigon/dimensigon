import typing as t
from datetime import datetime

from flask_jwt_extended import get_jwt_identity
from passlib.hash import sha256_crypt

from dimensigon import defaults
from dimensigon.domain.entities.base import UUIDistributedEntityMixin
from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import ScalarListType, UtcDateTime
from dimensigon.web import db

ROOT = '00000000-0000-0000-0000-000000000001'
OPS = '00000000-0000-0000-0000-000000000002'
REPORTER = '00000000-0000-0000-0000-000000000003'
JOIN = '00000000-0000-0000-0000-000000000004'


class User(UUIDistributedEntityMixin, db.Model):
    __tablename__ = 'D_user'

    name = db.Column(db.String(30), nullable=False)  # changed in SCHEMA VERSION 8
    _password = db.Column('password', db.String(256))
    email = db.Column(db.String)
    created_at = db.Column(UtcDateTime)
    active = db.Column('is_active', db.Boolean(), nullable=False)
    groups = db.Column(ScalarListType(str))

    __table_args__ = (db.UniqueConstraint('name'),)

    def __init__(self, name, password=None, email=None, created_at=None, active=True,
                 groups: t.Union[str, t.List[str]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self._password = password or kwargs.get('_password', None)
        self.email = email
        self.created_at = created_at or get_now()
        self.active = active
        if isinstance(groups, str):
            self.groups = groups.split(':')
        else:
            self.groups = groups or []

    @classmethod
    def get_by_name(cls, name):
        return cls.query.filter_by(name=name).one_or_none()

    @classmethod
    def get_by_group(cls, group):
        return [g for g in cls.query.all() if group in g.groups]

    def _hash_password(self, password):
        if not self._password:
            self._password = sha256_crypt.hash(password)

    def verify_password(self, password) -> bool:
        return sha256_crypt.verify(password, self._password)

    def set_password(self, password):
        self._password = None
        self._hash_password(password)

    def to_json(self, password=False, **kwargs) -> dict:
        data = super().to_json(**kwargs)
        data.update(name=self.name, email=self.email, created_at=self.created_at.strftime(defaults.DATETIME_FORMAT),
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
    def set_initial(cls, session=None):
        """

        Args:
            session: used when not in Flask context
        """
        from dimensigon.domain.entities import bypass_datamark_update

        if session is None:
            session = db.session

        with bypass_datamark_update(session):
            root = session.query(cls).filter_by(name='root').one_or_none()
            if not root:
                root = User(id=ROOT, name='root', groups=['administrator'],
                            last_modified_at=defaults.INITIAL_DATEMARK)
                session.add(root)
            ops = session.query(cls).filter_by(name='ops').one_or_none()
            if not ops:
                ops = User(id=OPS, name='ops', groups=['operator', 'deployer'],
                           last_modified_at=defaults.INITIAL_DATEMARK)
                session.add(ops)
            reporter = session.query(cls).filter_by(name='reporter').one_or_none()
            if not reporter:
                reporter = User(id=REPORTER, name='reporter', groups=['readonly'],
                                last_modified_at=defaults.INITIAL_DATEMARK)
                session.add(reporter)
            join = session.query(cls).filter_by(name='join').one_or_none()
            if not join:
                join = User(id=JOIN, name='join', groups=[''],
                            last_modified_at=defaults.INITIAL_DATEMARK)
                session.add(join)

    @classmethod
    def get_current(cls):
        return cls.query.get(get_jwt_identity())

    def __repr__(self):
        return f"{self.id}.{self.name}"

    def __str__(self):
        return self.name
