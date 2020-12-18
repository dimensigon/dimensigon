import copy
import datetime as dt
import ipaddress
import logging
import socket
import typing as t

from flask import current_app, url_for, g, has_app_context
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound

from dimensigon.utils.typos import ScalarListType, Gate as TGate, UtcDateTime, Id
from dimensigon.web import db, errors
from .base import UUIDistributedEntityMixin, SoftDeleteMixin
from .gate import Gate
from .route import Route, RouteContainer
from ... import defaults
from ...utils.helpers import get_ips, get_now, is_iterable_not_string

class Server(UUIDistributedEntityMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'D_server'
    order = 10

    name = db.Column(db.String(255), nullable=False, unique=True)
    granules = db.Column(ScalarListType())
    _me = db.Column("me", db.Boolean, default=False)
    _old_name = db.Column("$$name", db.String(255))
    l_ignore_on_lock = db.Column("ignore_on_lock", db.Boolean,
                                 default=False)  # ignore the server for locking when set
    created_on = db.Column(UtcDateTime(timezone=True))  # new in version 3

    route: t.Optional[Route] = db.relationship("Route", primaryjoin="Route.destination_id==Server.id", uselist=False,
                                               back_populates="destination", cascade="all, delete-orphan")
    gates: t.List[Gate]

    log_sources = db.relationship("Log", primaryjoin="Server.id==Log.src_server_id", back_populates="source_server")
    log_destinations = db.relationship("Log", primaryjoin="Server.id==Log.dst_server_id",
                                       back_populates="destination_server")
    files = db.relationship("File", back_populates="source_server")
    file_server_associations = db.relationship("FileServerAssociation", back_populates="destination_server")
    software_server_associations = db.relationship("SoftwareServerAssociation", back_populates="server")

    # software_list = db.relationship("SoftwareServerAssociation", back_populates="server")

    def __init__(self, name: str, granules: t.List[str] = None,
                 dns_or_ip: t.Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address] = None, port: int = None,
                 gates: t.List[t.Union[TGate, t.Dict[str, t.Any]]] = None, me: bool = False, created_on=None,
                 **kwargs):
        super().__init__(**kwargs)
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
        self.created_on = created_on or get_now()
        # create an empty route
        if not me and not self.deleted:
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
        try:
            scheme = 'http' if current_app.dm and 'keyfile' not in current_app.dm.config.http_conf else 'https'
        except:
            scheme = 'https'
        gate = None
        route = self.route
        if self._me and (route is None or route.cost is None):
            if len(self.localhost_gates) > 0:
                gate = self.localhost_gates[0]
            else:
                # current_app.logger.warning(
                #     f"No localhost set for '{self}'. Trying connection through another gate")
                if len(self.gates) == 0:
                    raise RuntimeError(f"No gate set for server '{self}'")
                gate = self.gates[0]
        elif getattr(route, 'cost', None) == 0:
            gate = route.gate
        elif getattr(route, 'proxy_server', None):
            gate = getattr(getattr(route.proxy_server, 'route', None), 'gate', None)

        if not gate:
            raise errors.UnreachableDestination(self, getattr(g, 'server', None))

        root_path = f"{scheme}://{gate}"

        if view is None:
            return root_path
        else:
            with current_app.test_request_context():
                return root_path + url_for(view, **values)

    @classmethod
    def get_neighbours(cls, exclude: t.Union[t.Union[Id, 'Server'], t.List[t.Union[Id, 'Server']]] = None, session=None) -> \
    t.List[
        'Server']:
        """returns neighbour servers

        Args:
            alive: if True, returns neighbour servers inside the cluster

        Returns:

        """
        if session:
            query = session.query(cls).filter_by(deleted=0)
        else:
            query = cls.query
        query = query.join(cls.route).filter(Route.cost == 0)
        if exclude:
            if isinstance(exclude, list):
                if isinstance(exclude[0], Server):
                    query = query.filter(Server.id.notin_([s.id for s in exclude]))
                else:
                    query = query.filter(Server.id.notin_(exclude))
            elif isinstance(exclude, Server):
                query = query.filter(Server.id != exclude.id)
            else:
                query = query.filter(Server.id != exclude)

        return query.order_by(cls.name).all()

    @classmethod
    def get_not_neighbours(cls, session=None) -> t.List['Server']:
        if session:
            query = session.query(cls).filter_by(deleted=0)
        else:
            query = cls.query
        return query.outerjoin(cls.route).filter(
            or_(or_(Route.cost > 0, Route.cost == None), cls.route == None)).filter(cls._me == False).order_by(
            cls.name).all()

    @classmethod
    def get_reachable_servers(cls, alive=False,
                              exclude: t.Union[t.Union[Id, 'Server'], t.List[t.Union[Id, 'Server']]] = None) -> t.List[
        'Server']:
        """returns list of reachable servers

        Args:
            alive: if True, returns servers inside the cluster
            exclude: filter to exclude servers

        Returns:
        list of all reachable servers
        """
        query = cls.query.join(cls.route).filter(Route.cost.isnot(None))
        if exclude:
            if is_iterable_not_string(exclude):
                c_exclude = [e.id if isinstance(e, Server) else e for e in exclude]
            else:
                c_exclude = [exclude.id if isinstance(exclude, Server) else exclude]
            query = query.filter(Server.id.notin_(c_exclude))

        if alive:
            query = query.filter(Server.id.in_([iden for iden in current_app.dm.cluster_manager.get_alive()]))

        return query.order_by(Server.name).all()

    def to_json(self, add_gates=False, human=False, add_ignore=False, **kwargs):
        data = super().to_json(**kwargs)
        data.update(
            {'name': self.name, 'granules': self.granules,
             'created_on': self.created_on.strftime(defaults.DATETIME_FORMAT)})
        if add_gates:
            data.update(gates=[])
            for g in self.gates:
                json_gate = g.to_json(human=human)
                json_gate.pop('server_id', None)
                json_gate.pop('server', None)  # added to remove when human set
                data['gates'].append(json_gate)
        if add_ignore:
            data.update(ignore_on_lock=self.l_ignore_on_lock or False)
        return data

    @classmethod
    def from_json(cls, kwargs) -> 'Server':
        kwargs = copy.deepcopy(kwargs)
        gates = kwargs.pop('gates', [])
        if 'created_on' in kwargs:
            kwargs['created_on'] = dt.datetime.strptime(kwargs['created_on'], defaults.DATETIME_FORMAT)
        server = super().from_json(kwargs)
        for gate in gates:
            gate.update(server=server)
            Gate.from_json(gate)
        return server

    @classmethod
    def get_current(cls, session=None) -> 'Server':
        if session is None:
            session = db.session
        return session.query(cls).filter_by(_me=True).filter_by(deleted=False).one()

    @staticmethod
    def set_initial(session=None, gates=None) -> Id:
        logger = logging.getLogger('dm.db')
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
            logger.info(f'Creating Server {server.name} with the following gates: {gates}')
            session.add(server)
            return server.id
        elif len(server) > 1:
            raise ValueError('Multiple servers found as me.')
        else:
            return server[0].id

    def ignore_on_lock(self, value: bool):
        if value != self.l_ignore_on_lock:
            from dimensigon.domain.entities import bypass_datamark_update
            with bypass_datamark_update:
                self.l_ignore_on_lock = value

    def set_route(self, proxy_route, gate=None, cost=None):
        if self.route is None:
            self.route = Route(destination=self)
        if isinstance(proxy_route, RouteContainer):
            self.route.set_route(proxy_route)
        elif isinstance(proxy_route, Route):
            assert proxy_route.destination == self
            self.route.set_route(RouteContainer(proxy_route.proxy_server, proxy_route.gate, proxy_route.cost))
        else:
            self.route.set_route(RouteContainer(proxy_route, gate, cost))

    def delete(self):
        super().delete()
        for g in self.gates:
            g.delete()
        for l in self.log_sources:
            l.delete()
        for l in self.log_destinations:
            l.delete()
        for ssa in self.software_server_associations:
            ssa.delete()
        for fsa in self.file_server_associations:
            fsa.delete()
        for f in self.files:
            f.delete()
