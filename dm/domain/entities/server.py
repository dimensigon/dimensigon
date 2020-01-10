import ipaddress
import uuid
import typing as t
from flask import current_app, url_for

from dm.utils.typos import UUID, IP, ScalarListType
from dm.web import db


class Server(db.Model):
    __tablename__ = 'L_server'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    ip = db.Column(IP, nullable=False)
    port = db.Column(db.Integer, nullable=False)
    granules = db.Column(ScalarListType)
    neighbour = db.Column(db.Boolean)
    mesh_best_route = db.Column(ScalarListType(uuid.UUID))
    mesh_alt_route = db.Column(ScalarListType(uuid.UUID))
    gateway_id = db.Column(UUID, db.ForeignKey('D_server.id'), )
    cost = db.Column(db.Integer)

    gateway = db.relationship("Server", uselist=False, remote_side=[id])

    def __init__(self, name: str, ip: t.Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address], port: int,
                 granules=None, neighbour: bool = None, mesh_best_route=None, mesh_alt_route=None,
                 id=uuid.uuid4(), gateway: 'Server' = None, cost: int = None):
        self.id = uuid.UUID(id) if isinstance(id, str) else id
        self.name = name
        self.ip = ipaddress.ip_address(ip) if isinstance(ip, str) else ip
        self.port = port
        self.neighbour = neighbour
        self.granules = granules or []
        self.mesh_best_route = mesh_best_route or []
        self.mesh_alt_route = mesh_alt_route or []
        self.gateway = gateway
        self.cost = cost

    def __str__(self):
        return self.name + ':' + str(self.port)
