import copy
import datetime as dt
import random
import threading
import typing as t

from dataclasses import dataclass

from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import Id

date_format = "%m/%d/%Y, %H:%M:%S %z"


@dataclass
class _ClusterRegister:
    id: Id
    birth: dt.datetime = None
    keepalive: dt.datetime = None
    death: dt.datetime = None
    coordinator: bool = False

    def to_dict(self, dateformat=date_format):
        data = {'id': self.id}
        if self.birth:
            data.update(birth=self.birth.strftime(dateformat))
        if self.keepalive:
            data.update(keepalive=self.keepalive.strftime(dateformat))
        if self.death:
            data.update(death=self.death.strftime(dateformat))
        if self.coordinator:
            data.update(coordinator=True)
        return data

    def __eq__(self, other: '_ClusterRegister'):
        if isinstance(other, self.__class__):
            return self.id == other.id and self.birth == other.birth \
                   and self.keepalive == other.keepalive \
                   and self.death == other.death \
                   and self.coordinator == other.coordinator
        else:
            return False

    @staticmethod
    def from_dict(dto, dateformat=date_format):
        ident = dto['id']
        if dto.get('birth', None):
            birth = dt.datetime.strptime(dto['birth'], dateformat)
        else:
            birth = None

        if dto.get('keepalive', None):
            keepalive = dt.datetime.strptime(dto['keepalive'], dateformat)
        else:
            keepalive = None

        if dto.get('death', None):
            death = dt.datetime.strptime(dto['death'], dateformat)
        else:
            death = None

        return _ClusterRegister(ident, birth=birth, keepalive=keepalive, death=death)


@dataclass
class _ClusterRegisterSession(_ClusterRegister):
    session: Id = None

    def to_dict(self, dateformat=date_format):
        data = super().to_dict(dateformat)
        data['session'] = self.session
        return data

    def __eq__(self, other: '_ClusterRegisterSession'):
        return super().__eq__(other) and self.session == other.session

    @classmethod
    def from_dict(cls, dto, dateformat=date_format):
        kwargs = dict(id=dto['id'], session=dto['session'])
        if dto.get('birth', None):
            kwargs['birth'] = dt.datetime.strptime(dto['birth'], dateformat)

        if dto.get('keepalive', None):
            kwargs['keepalive'] = dt.datetime.strptime(dto['keepalive'], dateformat)

        if dto.get('death', None):
            kwargs['death'] = dt.datetime.strptime(dto['death'], dateformat)

        return cls(**kwargs)


class Cluster(object):
    _register_class = _ClusterRegister
    _cluster: t.Dict[Id, type(_register_class)] = {}
    _lock = threading.RLock()

    def __init__(self, threshold=None):
        self.threshold = threshold or dt.timedelta()

    def __getitem__(self, iden):
        return self._cluster[iden].to_dict()

    def __contains__(self, iden):
        try:
            cr = self._cluster[iden]
        except KeyError:
            return False
        if cr.death is None:
            return True

    def __iter__(self):
        with self._lock:
            for cr in self._cluster.values():
                if cr.death is None:
                    yield cr.id

    def set_alive(self, iden: Id, alive=None) -> t.Optional[t.Dict]:
        with self._lock:
            alive = alive or get_now()
            initial_cr = copy.deepcopy(self._cluster.get(iden, None))
            if iden in self._cluster:
                if self._cluster[iden].death is not None:
                    if self._cluster[iden].birth < alive:
                        self._cluster[iden].birth = alive
                    self._cluster[iden].keepalive = alive
                    self._cluster[iden].death = None
                elif alive < self._cluster[iden].birth:
                    self._cluster[iden].birth = alive
                else:
                    return None
            else:
                self._cluster[iden] = self._register_class(iden, birth=alive, keepalive=alive)
            return self._cluster[iden].to_dict() if initial_cr != self._cluster[iden] else None

    def set_keepalive(self, iden: Id, keepalive=None) -> t.Optional[t.Dict]:
        with self._lock:
            keepalive = keepalive or get_now()
            initial_cr = copy.deepcopy(self._cluster.get(iden, None))
            if iden in self._cluster:
                if self._cluster[iden].death is not None:
                    self.set_alive(iden)
                if not self._cluster[iden].keepalive or self._cluster[iden].keepalive < keepalive - self.threshold:
                    self._cluster[iden].keepalive = keepalive
            else:
                self._cluster[iden] = self._register_class(iden, birth=keepalive, keepalive=keepalive)
            return self._cluster[iden].to_dict() if self._cluster[iden] != initial_cr else None

    def set_death(self, iden: Id, death=None) -> t.Optional[t.Dict]:
        with self._lock:
            death = death or get_now()
            if iden in self._cluster:
                cr = self._cluster[iden]
                if cr.death is None:
                    if death > cr.birth:
                        cr.death = death
                    else:
                        cr.death = cr.birth
                else:
                    if death and cr.death > death:
                        cr.death = death
                    else:
                        return None
            else:
                self._cluster[iden] = self._register_class(iden, birth=death, death=death)
            return self._cluster[iden].to_dict()

    def update_cluster(self, in_cr_list: t.Union[dict, list]) -> t.List[_ClusterRegister]:
        if isinstance(in_cr_list, list):
            return self._update_cluster([self._register_class.from_dict(cr) for cr in in_cr_list])
        else:
            return self._update_cluster([self._register_class.from_dict(in_cr_list)])

    def _update_cluster(self, in_cr_list: t.List[_ClusterRegister]):
        with self._lock:
            changed = []
            for in_cr in in_cr_list:
                updated = False
                if in_cr.id in self._cluster:
                    cr = self._cluster[in_cr.id]
                    if in_cr.birth > cr.birth:
                        self._cluster[in_cr.id] = in_cr
                        cr = self._cluster[in_cr.id]
                        updated = True
                    if in_cr.keepalive is not None and (cr.keepalive is None or in_cr.keepalive > cr.keepalive):
                        cr.keepalive = in_cr.keepalive
                        cr.death = None
                        updated = True
                    if in_cr.death is not None and cr.death is not None and in_cr.death > cr.death:
                        cr.death = in_cr.death
                        updated = True
                    if cr.death is None and in_cr.death is not None and in_cr.death > cr.birth:
                        cr.death = in_cr.death
                        updated = True
                    elif in_cr.birth is not None and cr.death is not None and in_cr.birth > cr.death:
                        cr.birth = in_cr.birth
                        cr.death = in_cr.death
                        updated = True
                else:
                    self._cluster[in_cr.id] = in_cr
                    updated = True
                if updated:
                    changed.append(in_cr.id)
            return changed

    def get_alive(self) -> t.List[Id]:
        with self._lock:
            return [cr.id for cr in self._cluster.values() if cr.birth is not None and cr.death is None]

    def get_delta_keepalive(self, delta: dt.timedelta):
        with self._lock:
            now = get_now()
            return [cr.id for cr in self._cluster.values() if
                    cr.birth is not None and cr.death is None and (now - (cr.keepalive or cr.birth)) < delta]

    def get_oldest_alive(self) -> t.Union[Id, None]:
        with self._lock:
            cr_list = [cr for cr in self._cluster.values() if cr.death is None]
            cr_list.sort(key=lambda x: x.birth)
            return cr_list[0].id

    def get_cluster(self) -> t.List[t.Dict]:
        with self._lock:
            return [cr.to_dict() for cr in self._cluster.values()]

    def get(self, iden) -> t.Dict:
        with self._lock:
            return self._cluster[iden].to_dict()

    # only for testing purposes
    def clear_cluster(self):
        self._cluster = {}


class ClusterKeepAlive(Cluster):

    def set_alive(self, iden: Id, alive=None) -> t.Optional[t.Dict]:
        with self._lock:
            alive = alive or get_now()
            if iden in self._cluster:
                if self._cluster[iden].death is not None:
                    self._cluster[iden].birth = alive
                    self._cluster[iden].death = None
                else:
                    self._cluster[iden].birth = alive
            else:
                self._cluster[iden] = self._register_class(iden, birth=alive)
            return self._cluster[iden].to_dict()


class ClusterCoordinator(Cluster):
    _cluster: t.Dict[Id, _ClusterRegisterSession] = {}
    _register_class = _ClusterRegister

    def set_alive(self, iden: Id) -> t.Dict:
        with self._lock:
            super().set_alive(iden)
            if not self.coordinators:
                self._cluster[iden].coordinator = True
            return self._cluster[iden].to_dict()

    def set_death(self, iden: Id, death=None) -> t.List[t.Dict]:
        with self._lock:
            death = super().set_death(iden, death)
            data = [death]
            if self._cluster[iden].coordinator:
                self._cluster[iden].coordinator = False
                death['coordinator'] = False
                new_coordinator = self.try_set_coordinator(self.get_oldest_alive())
                if new_coordinator:
                    data.append(self._cluster[self.get_oldest_coordinator()].to_dict())
            return data

    @property
    def coordinators(self) -> t.List[_ClusterRegister]:
        with self._lock:
            return [cr for cr in self._cluster.values() if cr.coordinator and cr.death is None]

    def get_coordinators(self) -> t.List[Id]:
        with self._lock:
            return [cr.id for cr in self._cluster.values() if cr.coordinator and cr.death is None]

    def get_oldest_coordinator(self) -> t.Union[Id, None]:
        with self._lock:
            coord_cr_list = [cr for cr in self._cluster.values() if cr.coordinator and cr.death is None]
        if coord_cr_list:
            coord_cr_list.sort(key=lambda x: x.birth)
            return coord_cr_list[0].id
        else:
            return None

    def try_set_coordinator(self, iden: Id):
        with self._lock:
            if not self.coordinators:
                self._cluster[iden].coordinator = True
                return True
            else:
                return False

    def set_coordinator(self, iden: Id):
        with self._lock:
            updated = False
            for cr in self._cluster.values():
                if cr.coordinator:
                    updated = True
                    cr.coordinator = False
            if not self._cluster[iden].coordinator:
                self._cluster[iden].coordinator = True
                updated = True
            return updated

    def _update_cluster(self, in_cr_list: t.List[_ClusterRegister]):
        with self._lock:
            updated = super()._update_cluster(in_cr_list)
            for in_cr in in_cr_list:
                if self._cluster[in_cr.id].death is None:
                    self._cluster[in_cr.id].coordinator = self._cluster[in_cr.id].coordinator or in_cr.coordinator
                    if in_cr.coordinator and not self._cluster[in_cr.id].coordinator:
                        updated = True

            # select oldest coordinators
            coordinator = self.get_oldest_coordinator()
            if coordinator is None:
                cr_l = list(self._cluster.values())
                cr_l.sort(key=lambda x: x.birth)
                if len(cr_l) > 0:
                    coordinator = cr_l[0].id
            if coordinator:
                coord_updated = self.set_coordinator(coordinator)

            return updated or coord_updated


class ClusterSession(Cluster):
    _register_class = _ClusterRegisterSession

    def __init__(self, threshold: dt.timedelta = None):
        self._session = None
        self.threshold = threshold

    def set_session(self):
        if self._session is None:
            self._session = int(random.random() * 1000000000000)

    @property
    def session(self):
        return self._session

    def set_alive(self, iden: Id, session: Id, alive=None) -> t.Optional[t.Dict]:
        with self._lock:
            alive = alive or get_now()
            if iden in self._cluster:
                if self._cluster[iden].session == session:
                    if self._cluster[iden].death is not None:
                        if alive < self._cluster[iden].birth:
                            self._cluster[iden].birth = alive
                        self._cluster[iden].keepalive = alive
                        self._cluster[iden].death = None
                    else:
                        return None
                else:
                    self._cluster[iden].session = session
                    self._cluster[iden].birth = alive
                    self._cluster[iden].keepalive = alive
                    self._cluster[iden].death = None
            else:
                self._cluster[iden] = self._register_class(iden, session=session, birth=alive, keepalive=alive)
            return self._cluster[iden].to_dict()

    def set_death(self, iden: Id, session: Id, death=None) -> t.Optional[t.Dict]:
        with self._lock:
            death = death or get_now()
            initial_cr = copy.deepcopy(self._cluster.get(iden, None))
            if iden in self._cluster:
                cr = self._cluster[iden]
                if self._cluster[iden].session == session:
                    if cr.death is None:
                        if death > cr.birth:
                            cr.death = death
                        else:
                            cr.death = cr.birth
                    else:
                        if death and cr.death > death:
                            cr.death = death
                        else:
                            return None
                else:

                    if cr.death is None:
                        if cr.birth < death:
                            self._cluster[iden].death = death
                            self._cluster[iden].birth = death
                            self._cluster[iden].session = session
                    else:
                        if cr.death < death:
                            self._cluster[iden].death = death
                            self._cluster[iden].birth = death
                            self._cluster[iden].session = session
            else:
                self._cluster[iden] = self._register_class(iden, session=session, birth=death, death=death)
            if initial_cr != self._cluster[iden]:
                return self._cluster[iden].to_dict()

    def set_keepalive(self, iden: Id, session: Id = None, keepalive=None) -> t.Optional[t.Dict]:
        with self._lock:
            keepalive = keepalive or get_now()
            if iden in self._cluster:
                if self._cluster[iden].session == session:
                    self.set_alive(iden, session, keepalive)
                self._cluster[iden].keepalive = keepalive
            else:
                self._cluster[iden] = self._register_class(iden, session=session, birth=keepalive, keepalive=keepalive)
            return self._cluster[iden].to_dict()

    def _update_cluster(self, in_cr_list: t.List[_ClusterRegisterSession]):
        with self._lock:
            updated = False
            for in_cr in in_cr_list:
                if in_cr.id in self._cluster:
                    cr = self._cluster[in_cr.id]
                    if cr.session == in_cr.session:
                        if in_cr.birth < cr.birth:
                            cr.birth = in_cr.birth
                            updated = True
                        if in_cr.keepalive is not None and (cr.keepalive is None or in_cr.keepalive > cr.keepalive):
                            cr.keepalive = in_cr.keepalive
                            updated = True
                        if in_cr.death is not None and cr.death is not None and in_cr.death < cr.death:
                            cr.death = in_cr.death
                            updated = True
                        if cr.death is None and in_cr.death is not None and in_cr.death > cr.birth:
                            cr.death = in_cr.death
                            updated = True
                        elif in_cr.birth is not None and cr.death is not None and in_cr.birth > cr.death:
                            cr.birth = in_cr.birth
                            cr.death = in_cr.death
                            updated = True
                    else:
                        # newer session is stored
                        if cr.birth < in_cr.birth:
                            self._cluster[in_cr.id] = in_cr
                            updated = True
                else:
                    self._cluster[in_cr.id] = in_cr
                    updated = True
            return updated
