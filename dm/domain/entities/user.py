from datetime import datetime

from passlib.hash import sha256_crypt

from dm import defaults
from dm.domain.entities.base import UUIDistributedEntityMixin
from dm.web import db


class Group(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_group'

    group = db.Column(db.String, nullable=False, primary_key=True)

    users = db.relationship("User", back_populates="groups")

    @classmethod
    def set_initial(cls):
        a = cls(group='administrator', last_modified_at=defaults.INITIAL_DATEMARK)
        o = cls(group='operator', last_modified_at=defaults.INITIAL_DATEMARK)
        d = cls(group='deployer', last_modified_at=defaults.INITIAL_DATEMARK)
        r = cls(group='readonly', last_modified_at=defaults.INITIAL_DATEMARK)
        db.session.add_all([a, o, d, r])


class User(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_user'

    user = db.Column(db.String(30), nullable=False)
    _password = db.Column('password', db.String(256))
    email = db.Column(db.Text)
    created_at = db.Column(db.Date, default=datetime.now())
    active = db.Column('is_active', db.Boolean(), nullable=False, default=True)

    groups = db.relationship("Group", back_populates="users")

    __table_args__ = (db.UniqueConstraint('user', name='D_user_uq01'),)

    def __init__(self, user, email=None, active=True, groups=None,  create_new_groups=False, **kwargs):
        super().__init__(**kwargs)
        self.user = user
        self.email = email
        self.groups = groups
        self.active = active
        self.groups = []
        for group in groups:
            if isinstance(group, Group):
                self.groups.append(group)
            else:
                g = Group.query.get(group)
                if g is None:
                    if create_new_groups:
                        g = Group(group=group)
                    else:
                        raise ValueError(f"Group '{group}' not found")
                self.groups.append(g)

    @classmethod
    def get_by_user(cls, user):
        return db.session.query(cls).filter_by(user=user).one_or_none()

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

    @classmethod
    def set_initial(cls):
        root = cls.get_by_user('root')
        if not root:
            root = User(user='root', groups=['administrator'], create_new_groups=True)
            root.hash_password('12345678')
            db.session.add(root)
        ops = cls.get_by_user('ops')
        if not ops:
            ops = User(user='ops', groups=['operator', 'deployer'], create_new_groups=True)
            db.session.add(ops)
        reporter = cls.get_by_user('reporter')
        if not reporter:
            reporter = User(user='reporter', groups=['readonly'], create_new_groups=True)
            db.session.add(reporter)
