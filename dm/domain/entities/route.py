import typing as t

from dm.network.low_level import check_host
from dm.utils.typos import UUID
from dm.web import db

if t.TYPE_CHECKING:
    from dm.domain.entities import Server, Gate


class Route(db.Model):
    __tablename__ = 'L_route'

    destination_id = db.Column(UUID, db.ForeignKey('D_server.id'), primary_key=True, nullable=False)
    proxy_server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    gate_id = db.Column(UUID, db.ForeignKey('D_gate.id'))
    cost = db.Column(db.Integer)

    destination = db.relationship("Server", foreign_keys=[destination_id], back_populates="route")
    proxy_server = db.relationship("Server", foreign_keys=[proxy_server_id])
    gate = db.relationship("Gate", foreign_keys=[gate_id])

    def __init__(self, destination: 'Server', proxy_server: 'Server' = None, gate: 'Gate' = None, cost: int = None):
        self.destination = destination
        if proxy_server:
            if proxy_server == destination:
                raise ValueError('You must specify a gate when proxy_server equals destination')
            else:
                if cost is None or cost == 0:
                    raise ValueError("Cost must be specified and greater than 0 when proxy_server")
                self.proxy_server = proxy_server
                self.cost = cost
        elif gate:
            # check if gate is from neighbour or from a proxy server
            if gate and destination == gate.server:
                if cost is not None and cost > 0:
                    raise ValueError("Cost must be set to 0 when defining route for a neighbour")
                self.gate = gate
                self.cost = 0
            else:
                if cost is None or cost <= 0:
                    raise ValueError("Cost must be specified and greater than 0 when gate from a proxy_server")
                else:
                    self.gate = gate
                    self.cost = cost
        elif cost == 0:
            # find a gateway and set that gateway as default
            if len(destination.external_gates) == 1:
                self.gate = destination.external_gates[0]
                self.cost = 0
            else:
                for gate in destination.external_gates:
                    if check_host(gate.dns or str(gate.ip), gate.port, timeout=1, retry=3, delay=0.5):
                        self.gate = gate
                        self.cost = 0
                        break
        # if not (self.gate or self.proxy_server):
        #     raise ValueError('Not a valid route')

    def __str__(self):
        gate = f"{self.gate.server}://{self.gate}" if self.gate else "None"
        return f"{self.destination} -> " \
               f"proxy_server={self.proxy_server}, " \
               f"gate={gate}, " \
               f"cost={self.cost}"

    def __repr__(self):
        return f"Route({self.to_json()})"

    def to_json(self):
        if not self.destination.id or (self.proxy_server and not self.proxy_server.id) or (
                self.gate and not self.gate.id):
            raise RuntimeError("commit object before dump to json")
        return {'destination_id': str(getattr(self.destination, 'id', '')) or None,
                'proxy_server_id': str(getattr(self.proxy_server, 'id', '')) or None,
                'gate_id': str(getattr(self.gate, 'id', '')) or None,
                'cost': self.cost}
