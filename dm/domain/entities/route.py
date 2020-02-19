import sqlalchemy as sa
from sqlalchemy.orm import relationship

from dm.model import Base
from dm.utils.typos import UUID


class Route(Base):
    __tablename__ = 'L_route'

    destination_id = sa.Column(UUID, sa.ForeignKey('D_server.id'), primary_key=True, nullable=False)
    gateway_id = sa.Column(UUID, sa.ForeignKey('D_server.id'))
    cost = sa.Column(sa.Integer)

    destination = relationship("Server", foreign_keys=[destination_id], back_populates="route")
    gateway = relationship("Server", foreign_keys=[gateway_id])

    def __str__(self):
        return f"Route(destination={getattr(self.destination, 'id', None)}, gateway={getattr(self.gateway, 'id', None)})"

    def __repr__(self):
        return str(self)

    def to_dict(self):
        return {'destination': getattr(self.destination, 'id', None), 'gateway': getattr(self.gateway, 'id', None),
                'cost': self.cost}

    def to_json(self):
        return {'destination': str(getattr(self.destination, 'id', '')) or None,
                'gateway': str(getattr(self.gateway, 'id', '')) or None,
                'cost': self.cost}
