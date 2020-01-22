import ipaddress
import typing as t
import uuid

from flask import current_app, url_for, g
from sqlalchemy import or_

from dm.utils.typos import UUID, IP, ScalarListType
from dm.web import db
from .base import DistributedEntityMixin, EntityReprMixin
from .route import Route


class Server(db.Model, EntityReprMixin, DistributedEntityMixin):
    __tablename__ = 'D_server'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    ip = db.Column(IP, nullable=False)
    port = db.Column(db.Integer, nullable=False)
    dns_name = db.Column(db.String(255))
    granules = db.Column(ScalarListType())

    route = db.relationship("Route", primaryjoin="Route.destination_id==Server.id", uselist=False,
                            back_populates="destination")
    software_list = db.relationship("SoftwareServerAssociation", back_populates="server")

    def __init__(self, name: str, ip: t.Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address], port: int,
                 dns_name: str = None, granules=None, gateway: 'Server' = None, cost: int = None, id: uuid.UUID = None,
                 **kwargs):
        DistributedEntityMixin.__init__(self, **kwargs)
        self.id = id
        self.name = name
        self.ip = ipaddress.ip_address(ip) if isinstance(ip, str) else ip
        self.port = port
        self.dns_name = dns_name
        self.granules = granules or []
        if (gateway or cost) and cost > 0 and gateway is None:
            raise AttributeError("'gateway' must be specified if 'cost' greater than 0")
        self.route = Route(gateway=gateway, cost=cost)

    def __str__(self):
        return f"{self.name} {self.id}"

    def url(self, view: str=None, **values) -> str:
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
        scheme = current_app.config['PREFERRED_URL_SCHEME']
        if self.cost == 0:
            root_path = f"{scheme}://{self.dns_name or self.ip}:{self.port}"
        elif self.gateway:
            root_path = f"{scheme}://{self.gateway.dns_name or self.gateway.ip}:{self.gateway.port}"
        else:
            raise ConnectionError(f"Unreachable destination {self.id}")
        if view is None:
            return root_path
        else:
            return root_path + url_for(view, **values, _external=False)

    @classmethod
    def get_neighbours(cls) -> t.List['Server']:
        return cls.query.join(Route.destination).filter(Route.cost == 0).all()

    @classmethod
    def get_not_neighbours(cls) -> t.List['Server']:
        return cls.query.join(Route.destination).filter(or_(Route.cost > 0, Route.cost == None)).filter(
            Server.id != g.server.id).all()

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'ip': self.ip, 'port': self.port, 'granules': self.granules}

    def to_json(self):
        return {'id': str(self.id), 'name': self.name, 'ip': str(self.ip), 'port': self.port, 'granules': self.granules}
