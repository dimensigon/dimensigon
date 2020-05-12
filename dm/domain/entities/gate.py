import copy
import ipaddress
import typing as t

from dm.domain.entities.base import UUIDistributedEntityMixin
from dm.utils.typos import UUID, IP as IPType
from dm.web import db

if t.TYPE_CHECKING:
    from dm.domain.entities import Server


class Gate(db.Model, UUIDistributedEntityMixin):
    __tablename__ = "D_gate"
    order = 20

    server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    dns = db.Column(db.String(100))
    ip = db.Column(IPType)
    port = db.Column(db.Integer, nullable=False)

    __table_args__ = (db.UniqueConstraint('server_id', 'ip', 'dns'),)

    server = db.relationship("Server", back_populates="gates")

    def __init__(self, server: 'Server', port: int, dns: str = None,
                 ip: t.Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address] = None, **kwargs):
        UUIDistributedEntityMixin.__init__(self, **kwargs)
        self.server = server
        self.port = port
        self.ip = ipaddress.ip_address(ip) if isinstance(ip, str) else ip
        self.dns = dns
        if not (self.dns or self.ip):
            self.dns = server.name

    def __str__(self):
        return f'{self.dns or self.ip}:{self.port}'

    def to_json(self, human=False):
        data = super().to_json()
        data.update(server_id=str(self.server.id) if self.server.id else None, ip=str(self.ip) if self.ip else None,
                    dns=self.dns, port=self.port)
        return data

    @classmethod
    def from_json(cls, kwargs):
        from dm.domain.entities import Server
        server = kwargs.pop('server', None)
        kwargs = copy.deepcopy(kwargs)
        if server:
            kwargs['server'] = server
        kwargs['ip'] = ipaddress.ip_address(kwargs.get('ip')) if isinstance(kwargs.get('ip'), str) else kwargs.get('ip')
        if 'server_id' in kwargs and kwargs['server_id'] is not None:
            kwargs['server'] = Server.query.filter_by(id=kwargs.get('server_id')).one()
            kwargs.pop('server_id')
        return super().from_json(kwargs)
