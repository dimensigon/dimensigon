import copy
import ipaddress
import os
import typing as t

from flask import current_app, url_for
from sqlalchemy import or_

from dm.utils.typos import IP, ScalarListType
from dm.web import db
from .base import UUIDistributedEntityMixin
from .route import Route
from ... import defaults


# TODO: handle multiple networks (IP gateways) on a server with netifaces
class Server(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_server'
    order = 10

    name = db.Column(db.String(255), nullable=False)
    ip = db.Column(IP)
    port = db.Column(db.Integer, nullable=False)
    dns_name = db.Column(db.String(255))
    granules = db.Column(ScalarListType())
    _me = db.Column("me", db.Boolean, default=False)

    route = db.relationship("Route", primaryjoin="Route.destination_id==Server.id", uselist=False,
                            back_populates="destination")

    # software_list = db.relationship("SoftwareServerAssociation", back_populates="server")

    __table_args__ = (db.UniqueConstraint('name', name='D_server_uq01'),)

    def __init__(self, name: str, ip: t.Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address] = None,
                 port: int = 5000,
                 dns_name: str = None, granules=None, gateway: 'Server' = None, cost: int = None,
                 me=False, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.ip = ipaddress.ip_address(ip) if isinstance(ip, str) else ip
        self.port = port
        self.dns_name = dns_name
        # if not (self.ip and self.dns_name):
        #     raise ValueError("ip or dns_name must be specified")
        self.granules = granules or []
        self._me = me
        if (gateway or cost) and cost > 0 and gateway is None:
            raise ValueError("'gateway' must be specified if 'cost' greater than 0")
        self.route = Route(destination=self, gateway=gateway, cost=cost)

    def __str__(self):
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
        scheme = current_app.config['PREFERRED_URL_SCHEME'] or 'http'
        if self.route.cost == 0:
            root_path = f"{scheme}://{self.dns_name or self.ip or self.name}:{self.port}"
        elif self.route.gateway:
            root_path = f"{scheme}://{self.route.gateway.dns_name or self.route.gateway.ip}:{self.route.gateway.port}"
        elif self.id == self.get_current().id:
            root_path = f"{scheme}://127.0.0.1:{defaults.LOOPBACK_PORT}"
        else:
            raise ConnectionError(f"Unreachable destination {self.id}")
        if view is None:
            return root_path
        else:
            with current_app.test_request_context():
                return root_path + url_for(view, **values)

    @classmethod
    def get_neighbours(cls) -> t.List['Server']:
        return db.session.query(cls).join(Route.destination).filter(Route.cost == 0).all()

    @classmethod
    def get_not_neighbours(cls) -> t.List['Server']:
        return db.session.query(cls).join(Route.destination).filter(or_(Route.cost > 0, Route.cost == None)).filter(
            Server._me == False).all()

    def to_json(self):
        data = super().to_json()
        data.update(
            {'name': self.name, 'ip': str(self.ip) if self.ip else None,
             'port': self.port, 'dns_name': self.dns_name,
             'granules': self.granules})
        return data

    @classmethod
    def from_json(cls, kwargs):
        kwargs = copy.deepcopy(kwargs)
        kwargs['ip'] = ipaddress.ip_address(kwargs.get('ip')) if isinstance(kwargs.get('ip'), str) else kwargs.get('ip')
        return super().from_json(kwargs)

    @classmethod
    def get_current(cls):
        return db.session.query(cls).filter_by(_me=True).one()

    @staticmethod
    def set_initial():
        server = Server.query.filter_by(_me=True).all()
        if len(server) == 0:
            server_name = current_app.config.get('SERVER_NAME') or defaults.HOSTNAME
            ip = os.environ.get('SERVER_HOST') or defaults.IP
            if ip == '0.0.0.0':
                ip = defaults.IP
            server = Server(name=server_name,
                            port=5000,
                            ip=None, me=True)
            db.session.add(server)
        elif len(server) > 1:
            raise ValueError('Multiple servers found as me.')
