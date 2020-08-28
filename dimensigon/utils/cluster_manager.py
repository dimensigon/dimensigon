import datetime as dt
import threading
import typing as t
from dataclasses import dataclass

from dimensigon import defaults
from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import Id


@dataclass
class _ClusterRegister:
    id: Id
    birth: dt.datetime = None
    death: dt.datetime = None
    coordinator: bool = False

    def to_dict(self):
        data = dict(id=self.id, birth=self.birth.strftime(defaults.DATEMARK_FORMAT))
        if self.death:
            data.update(death=self.death.strftime(defaults.DATEMARK_FORMAT))
        if self.coordinator:
            data.update(coordinator=True)
        return data

    def __eq__(self, other: '_ClusterRegister'):
        if isinstance(other, self.__class__):
            return self.id == other.id and self.birth == other.birth and self.death == other.death \
                   and self.coordinator == other.coordinator
        else:
            return False

    @staticmethod
    def from_dict(dto):
        iden = dto['id']
        birth = dt.datetime.strptime(dto['birth'], defaults.DATEMARK_FORMAT)
        death = dto.get('death', None)
        if death:
            death = dt.datetime.strptime(death, defaults.DATEMARK_FORMAT)
        return _ClusterRegister(iden, birth, death)

class ClusterManager(object):
    _cluster: t.Dict[Id, _ClusterRegister] = {}
    _lock = threading.Lock()

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

    def set_alive(self, iden: Id) -> t.Optional[t.Dict]:
        with self._lock:
            if iden in self._cluster:
                if self._cluster[iden].death is not None:
                    self._cluster[iden].birth = get_now()
                    self._cluster[iden].death = None
                else:
                    return None
            else:
                self._cluster[iden] = _ClusterRegister(iden, get_now())
            return self._cluster[iden].to_dict()

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
                self._cluster[iden] = _ClusterRegister(iden, death, death)
            return self._cluster[iden].to_dict()

    def update_cluster(self, in_cr_list: t.Union[dict, list]):
        if isinstance(in_cr_list, list):
            return self._update_cluster([_ClusterRegister.from_dict(cr) for cr in in_cr_list])
        else:
            return self._update_cluster([_ClusterRegister.from_dict(in_cr_list)])

    def _update_cluster(self, in_cr_list: t.List[_ClusterRegister]):
        with self._lock:
            updated = False
            for in_cr in in_cr_list:
                if in_cr.id in self._cluster:
                    cr = self._cluster[in_cr.id]
                    # get older data
                    if in_cr.birth < cr.birth:
                        cr.birth = in_cr.birth
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
                    self._cluster[in_cr.id] = in_cr
                    updated = True
            return updated

    def get_alive(self) -> t.List[Id]:
        with self._lock:
            return [cr.id for cr in self._cluster.values() if cr.birth is not None and cr.death is None]

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


class ClusterManagerCoordinator(ClusterManager):
    _cluster: t.Dict[Id, _ClusterRegister] = {}
    _lock = threading.RLock()

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