import typing as t

from dimensigon.domain.entities import User
from dimensigon.domain.entities.base import DistributedEntityMixin, SoftDeleteMixin
from dimensigon.utils.typos import UUID, Id
from dimensigon.web import db


class Vault(DistributedEntityMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'D_vault'

    user_id = db.Column(UUID, db.ForeignKey('D_user.id'), primary_key=True)
    scope = db.Column(db.String(100), primary_key=True, default='global')
    name = db.Column(db.String(100), primary_key=True)
    _old_name = db.Column(db.String(100))
    value = db.Column(db.PickleType)

    user = db.relationship("User")

    def to_json(self, human=False, **kwargs):
        dto = super().to_json(**kwargs)
        dto.update(name=self.name, value=self.value)
        if self.scope:
            dto.update(scope=self.scope)
        if human:
            dto.update(user={'id': self.user.id, 'name': self.user.name})
        else:
            dto.update(user_id=self.user_id or getattr(self.user, 'id', None))
        return dto

    @classmethod
    def from_json(cls, kwargs):
        super().from_json(kwargs)
        kwargs['user'] = User.query.get_or_raise(kwargs.pop('user_id', None))
        o = cls.query.get((getattr(kwargs.get('user'), 'id'), kwargs.get('scope', 'global'), kwargs.get('name')))
        if o:
            for k, v in kwargs.items():
                if getattr(o, k) != v:
                    setattr(o, k, v)
            return o
        else:
            return cls(**kwargs)

    @classmethod
    def get_variables_from(cls, user: t.Union[Id, User], scope='global'):
        if isinstance(user, User):
            user_id = user.id
        else:
            user_id = user
        return {vault.name: vault.value for vault in cls.query.filter_by(user_id=user_id, scope=scope).all()}

    def __str__(self):
        return f"Vault({self.user}:{self.scope}[{self.name}={self.value}])"
