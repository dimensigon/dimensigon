import typing as t

from dimensigon.network.low_level import check_host
from dimensigon.utils.typos import UUID
from dimensigon.web import db, errors

if t.TYPE_CHECKING:
    from dimensigon.domain.entities import Server, Gate


class RouteContainer:

    def __init__(self, proxy_server: t.Optional['Server'], gate: t.Optional['Gate'], cost: t.Optional[int]):
        self.proxy_server = proxy_server
        self.gate = gate
        self.cost = cost

    def __str__(self):
        return f"proxy_server={getattr(self.proxy_server, 'name', None)}, gate={self.gate}, cost={self.cost}"

    def __repr__(self):
        return f"RouteContainer(proxy_server={getattr(self.proxy_server, 'id', None)}, " \
               f"gate={getattr(self.gate, 'id', None)}, cost={self.cost}"

    def __iter__(self):
        yield self.proxy_server
        yield self.gate
        yield self.cost

    def __getitem__(self, item):
        if item == 0:
            return self.proxy_server
        elif item == 1:
            return self.gate
        elif item == 2:
            return self.cost
        else:
            IndexError('list index out of range')

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.cost == other.cost and self.gate == other.gate \
               and self.proxy_server == other.proxy_server


class Route(db.Model):
    __tablename__ = 'L_route'

    destination_id = db.Column(UUID, db.ForeignKey('D_server.id'), primary_key=True, nullable=False)
    proxy_server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    gate_id = db.Column(UUID, db.ForeignKey('D_gate.id'))
    cost = db.Column(db.Integer)

    destination = db.relationship("Server", foreign_keys=[destination_id], back_populates="route", lazy='joined')
    proxy_server = db.relationship("Server", foreign_keys=[proxy_server_id], lazy='joined')
    gate = db.relationship("Gate", foreign_keys=[gate_id], lazy='joined')

    def __init__(self, destination: 'Server', proxy_server_or_gate: t.Union['Server', 'Gate'] = None, cost: int = None):
        # avoid cycle import
        from dimensigon.domain.entities import Server
        self.destination = destination
        if isinstance(proxy_server_or_gate, Server):
            proxy_server = proxy_server_or_gate
            gate = None
        else:
            proxy_server = None
            gate = proxy_server_or_gate
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
            if destination == gate.server:
                if cost is not None and cost > 0:
                    raise ValueError("Cost must be set to 0 when defining route for a neighbour")
                self.gate = gate
                self.cost = 0
            else:
                if cost is None or cost <= 0:
                    raise ValueError("Cost must be specified and greater than 0 when gate is from a proxy_server")
                else:
                    self.proxy_server = gate.server
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

    def validate_route(self, rc: RouteContainer):
        if rc.proxy_server:
            if not (rc.gate is None and rc.cost > 0):
                raise errors.InvalidRoute(self.destination, rc)
            if rc.proxy_server._me:
                raise errors.InvalidRoute(self.destination, rc)
        elif rc.gate:
            if not rc.cost == 0:
                raise errors.InvalidRoute(self.destination, rc)
        else:
            if rc.cost is not None:
                raise errors.InvalidRoute(self.destination, rc)

    def set_route(self, rc: RouteContainer):
        self.validate_route(rc)
        self.proxy_server, self.gate, self.cost = rc

    def __str__(self):
        return f"{self.destination} -> " \
               f"{self.proxy_server or self.gate}, {self.cost}"

    def __repr__(self):
        return f"Route({self.to_json()})"

    def to_json(self, human=False):
        if not self.destination.id or (self.proxy_server and not self.proxy_server.id) or (
                self.gate and not self.gate.id):
            raise RuntimeError("commit object before dump to json")
        if human:
            return {'destination': str(self.destination) if self.destination else None,
                    'proxy_server': str(self.proxy_server) if self.proxy_server else None,
                    'gate': str(self.gate) if self.gate else None,
                    'cost': self.cost}
        else:
            return {'destination_id': self.destination_id,
                    'proxy_server_id': self.proxy_server_id,
                    'gate_id': self.gate_id,
                    'cost': self.cost}
