import copy
import ipaddress
import socket
import typing as t

from flask import current_app, url_for, g
from sqlalchemy import or_

from dimensigon.utils.typos import ScalarListType, Gate as TGate
from dimensigon.web import db, errors
from .base import UUIDistributedEntityMixin
from .gate import Gate
from .route import Route
from ... import defaults
# TODO: handle multiple networks (IP gateways) on a server with netifaces
from ...utils.helpers import get_ips


class Server(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_server'
    order = 10

    name = db.Column(db.String(255), nullable=False, unique=True)
    granules = db.Column(ScalarListType())
    _me = db.Column("me", db.Boolean, default=False)

    route = db.relationship("Route", primaryjoin="Route.destination_id==Server.id", uselist=False,
                            back_populates="destination", cascade="all, delete-orphan")
    gates = db.relationship("Gate", back_populates="server", cascade="all, delete-orphan")

    # software_list = db.relationship("SoftwareServerAssociation", back_populates="server")

    def __init__(self, name: str, granules: t.List[str] = None,
                 dns_or_ip: t.Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address] = None, port: int = None,
                 gates: t.List[t.Union[TGate, t.Dict[str, t.Any]]] = None, me: bool = False, **kwargs):
        UUIDistributedEntityMixin.__init__(self, **kwargs)
        self.name = name
        if port or dns_or_ip:
            self.add_new_gate(dns_or_ip or self.name, port or defaults.DEFAULT_PORT)

        if gates:
            for gate in gates:
                if isinstance(gate, str):
                    if ':' in gate:
                        self.add_new_gate(*gate.split(':'))
                    else:
                        self.add_new_gate(gate, defaults.DEFAULT_PORT)
                elif isinstance(gate, tuple):
                    self.add_new_gate(*gate)
                elif isinstance(gate, dict):
                    gate['server'] = self
                    Gate.from_json(gate)

        assert 'all' not in (granules or [])
        self.granules = granules or []
        self._me = me
        # create an empty route
        if not me:
            Route(self)

    @property
    def external_gates(self):
        e_g = []
        for g in self.gates:
            if not g.ip:
                try:
                    ip = ipaddress.ip_address(
                        socket.getaddrinfo(g.dns, 0, family=socket.AF_INET, proto=socket.IPPROTO_TCP)[0][4][0])
                except socket.gaierror:
                    e_g.append(g)
                    continue
                except KeyError:
                    e_g.append(g)
                    continue
            else:
                ip = g.ip
            if not ip.is_loopback:
                e_g.append(g)
        return e_g

    @property
    def localhost_gates(self):
        l_g = []
        for g in self.gates:
            if not g.ip:
                try:
                    ip = ipaddress.ip_address(
                        socket.getaddrinfo(g.dns, 0, family=socket.AF_INET, proto=socket.IPPROTO_TCP)[0][4][0])
                except socket.gaierror:
                    continue
                except KeyError:
                    continue
            else:
                ip = g.ip
            if ip.is_loopback:
                l_g.append(g)
        return l_g

    @property
    def hidden_gates(self):
        hg = [g for g in self.gates if g.hidden]
        hg.sort(key=lambda x: x.last_modified_at or get_now())
        return hg

    def add_new_gate(self, dns_or_ip: t.Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address], port: int,
                     hidden=None):
        ip = None
        dns = None
        if dns_or_ip:
            try:
                ip = ipaddress.ip_address(dns_or_ip)
            except ValueError:
                dns = dns_or_ip
        return Gate(server=self, port=port, dns=dns, ip=ip, hidden=hidden)

    def __str__(self, ):
        return f"{self.name}"

    def url(self, view: str = None, **values) -> str:
        """
        generates the full url to access the server. Uses url_for to generate the full_path.

        Parameters
        ----------
        view
        values

        Raises
        -------
        ConnectionError:
            if server is unreachable
        """
        scheme = current_app.config['PREFERRED_URL_SCHEME'] or 'https'
        gate = None
        # route = Route.query.filter_by(destination_id=self.id)
        route = self.route
        if self._me and (route is None or route.cost is None):
            try:
                gate = self.localhost_gates[0]
            except IndexError:
                current_app.logger.warning(
                    f"No localhost set for '{self}'. Trying connection through another gate")
                if len(self.gates) == 0:
                    raise RuntimeError(f"No gate set for server '{self}'")
                gate = self.gates[0]
        elif route is not None and route.cost == 0:
            gate = route.gate
        else:
            if route.proxy_server:
                gate = route.proxy_server.route.gate

        if not gate:
            raise errors.UnreachableDestination(self, getattr(g, 'server', None))

        root_path = f"{scheme}://{gate}"

        if view is None:
            return root_path
        else:
            with current_app.test_request_context():
                return root_path + url_for(view, **values)

    @classmethod
    def get_neighbours(cls) -> t.List['Server']:
        return db.session.query(cls).join(cls.route).filter(Route.cost == 0).all()

    @classmethod
    def get_not_neighbours(cls) -> t.List['Server']:
        return db.session.query(cls).outerjoin(cls.route).filter(
            or_(or_(Route.cost > 0, Route.cost == None), cls.route == None)).filter(Server._me == False).all()

    def to_json(self, add_gates=False, human=False):
        data = super().to_json()
        data.update(
            {'name': self.name, 'granules': self.granules})
        if add_gates:
            data.update(gates=[])
            for g in self.gates:
                json_gate = g.to_json(human=human)
                json_gate.pop('server_id', None)
                json_gate.pop('server', None) # added to remove when human set
                data['gates'].append(json_gate)
        return data

    @classmethod
    def from_json(cls, kwargs) -> 'Server':
        kwargs = copy.deepcopy(kwargs)
        gates = kwargs.pop('gates', [])
        server = super().from_json(kwargs)
        for gate in gates:
            gate.update(server=server)
            Gate.from_json(gate)
        return server

    @classmethod
    def get_current(cls) -> 'Server':
        return db.session.query(cls).filter_by(_me=True).one()

    @staticmethod
    def set_initial(session=None, gates=None):
        if session is None:
            session = db.session
        server = session.query(Server).filter_by(_me=True).all()
        if len(server) == 0:

            try:
                server_name = current_app.config.get('SERVER_NAME') or defaults.HOSTNAME
            except:
                server_name = defaults.HOSTNAME

            if gates is None:
                gates = [(ip, defaults.DEFAULT_PORT) for ip in get_ips()]
            server = Server(name=server_name,
                            gates=gates,
                            me=True)
            session.add(server)
        elif len(server) > 1:
            raise ValueError('Multiple servers found as me.')
