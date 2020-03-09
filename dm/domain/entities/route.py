from dm.utils.typos import UUID
from dm.web import db


class Route(db.Model):
    __tablename__ = 'L_route'

    destination_id = db.Column(UUID, db.ForeignKey('D_server.id'), primary_key=True, nullable=False)
    gateway_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    cost = db.Column(db.Integer)

    destination = db.relationship("Server", foreign_keys=[destination_id], back_populates="route")
    gateway = db.relationship("Server", foreign_keys=[gateway_id])

    def __init__(self, destination, gateway, cost):
        self.destination = destination
        self.gateway = gateway
        self.cost = cost

    def __str__(self):
        return f"Route(destination={getattr(self.destination, 'id', None)}, " \
               f"gateway={getattr(self.gateway, 'id', None)}, " \
               f"cost={self.cost})"

    def __repr__(self):
        return str(self)

    def to_dict(self):
        return {'destination': getattr(self.destination, 'id', None), 'gateway': getattr(self.gateway, 'id', None),
                'cost': self.cost}

    def to_json(self):
        return {'destination': str(getattr(self.destination, 'id', '')) or None,
                'gateway': str(getattr(self.gateway, 'id', '')) or None,
                'cost': self.cost}
