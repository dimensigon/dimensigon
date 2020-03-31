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
    email = db.Column(db.Text)
    created_at = db.Column(db.Date, default=datetime.now())
    active = db.Column('is_active', db.Boolean(), nullable=False, default=True)
    groups = db.Column(ScalarListType(str), default=[])

    __table_args__ = (db.UniqueConstraint('user', name='D_user_uq01'),)

    def get_by_user(self, user):
        return self.query.filter_by(user=user).one_or_none()

    def hash_password(self, password):
        if not self._password:
            self._password = sha256_crypt.encrypt(password)

    def verify_password(self, password):
        return sha256_crypt.verify(password, self._password)

    def set_password(self, password):
        self._password = None
        self.hash_password(password)

    def to_json(self, password=False):
        data = super().to_json()
        data.update(user=self.user, email=self.email, created_at=self.created_at.strftime(defaults.DATETIME_FORMAT),
                    active=self.active, groups=','.join(self.groups))
        if password:
            data.update(password=self._password)
        return data

    def set_initial(self):
        root = self.get_by_user('root')
        if not root:
            root = User(user='root', groups=['administrator'])
            db.session.add(root)
        ops = self.get_by_user('ops')
        if not ops:
            ops = User(user='ops', groups=['operator', 'deployer'])
            db.session.add(ops)
        reporter = self.get_by_user('reporter')
        if not reporter:
            reporter = User(user='reporter', groups=['readonly'])
            db.session.add(reporter)
