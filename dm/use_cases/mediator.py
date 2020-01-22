import asyncio
import datetime
import inspect
import json
import os
import typing as t
from dataclasses import dataclass
from random import random

from flask import g

import dm.domain.exceptions as de
import dm.use_cases.exceptions as ue
from dm.domain.entities import Server, Dimension, Catalog
from dm.network import TypeMsg
from dm.network import gateway as gtw
from dm.use_cases.base import Token, Scope
from dm.use_cases.deployment import Command
from dm.utils.helpers import get_now, get_distributed_entities
from dm.utils.typos import Callback, Kwargs


class SessionExpired(BaseException):
    pass


class SessionManager:
    """
    Session Manager Class. This class is a context Manager that returns the session related to a messageDTO
    """

    class Session:
        """
        Session Class. Allows to save session information
        """
        INITIAL_TTL = 3000

        def __init__(self, id_: int, ttl: int = None):
            """

            Parameters
            ----------
            id_:
                Session ID
            ttl:
                time in seconds that the session will be alive
            """
            self.__id = id_
            self.__ttl = ttl or self.INITIAL_TTL
            self.__expires = get_now() + datetime.timedelta(seconds=self.__ttl)

        @property
        def id(self):
            return self.__id

        @property
        def expiration(self):
            return self.__expires

        def renew(self, ttl=None):
            self.__expires = get_now() + datetime.timedelta(seconds=ttl or self.__ttl)

        def __getattr__(self, item):
            if item in self.__dict__:
                return self.__dict__[item]
            else:
                raise AttributeError(f"'Session' object has no attribute '{item}'")

        def __setattr__(self, key, value):
            self.__dict__[key] = value

    _session_pool: t.Dict[int, Session] = dict()

    @staticmethod
    def _get_random_session():
        return int(random() * 10000000000000000)

    def __init__(self, carrier: t.Any):
        if not carrier.session:
            id_ = self._get_random_session()
            self.session = self.Session(id_)
            self._session_pool[self.session.id] = self.session
            carrier.session = self.session.id
        else:
            if carrier.session not in self._session_pool:
                self._session_pool[carrier.session] = self.Session(carrier.session)
                self.session = self._session_pool[carrier.session]
            else:
                if self._session_pool[carrier.session].expiration <= get_now():
                    del self._session_pool[carrier.session]
                    raise SessionExpired(f'Session {carrier.session} has expired')
                else:
                    self.session = self._session_pool[carrier.session]

    @classmethod
    def clear_session_pool(cls):
        cls._session_pool.clear()

    def purge_session_pool(self):
        """
        Deletes sessions that have expired

        Returns
        -------

        """
        for s in list(self._session_pool.values()):
            if s.expiration <= get_now():
                del self._session_pool[s.id]

    def remove_session_pool(self):
        self._session_pool.clear()

    def set_ttl(self, value: int):
        """
        Sets the default ttl to the new sessions

        Parameters
        ----------
        value:
            seconds until the session gets expired after creation

       """
        self.Session.INITIAL_TTL = value

    def __enter__(self):
        # TODO LOW Implement an independent purge session pool into a thread
        self.purge_session_pool()
        return self._session_pool[self.session.id]

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session_pool[self.session.id].renew()


@dataclass
class Mapper:
    applicant: t.Any
    destination: Server = None
    session: str = None
    token: Token = None
    callback: Callback = None


class AttributeFilterList(t.List):
    """
    List class with a special method get_by to find an item with the specified attribute value
    """

    def get_by(self, attribute: str, search: t.Any) -> t.Any:
        """
        get items from list filtered by the search value of the attribute
        Parameters
        ----------
        attribute:
            attribute to search
        search:
            value of the attribute to filter the list

        Returns
        -------
        t.Any:
            obj that satisfies the filter. Only one object must match

        Raises
        ------
        KeyError:
            if no item matched
        LookupError:
            if more than one item matched
        """
        matched = [obj for obj in self if getattr(obj, attribute, None) == search]
        if len(matched) == 0:
            raise KeyError(f"{attribute} '{search}' not found")
        elif len(matched) > 1:
            raise LookupError(f"multiple Holders found for {attribute} '{search}'")
        return matched[0]


class Mediator:

    def __init__(self, interactor: 'Interactor', server: 'Server' = None,
                 dimension: 'Dimension' = None):
        self._mapper = AttributeFilterList()
        self._interactor = interactor
        try:
            self.server = server or g.server
        except RuntimeError:
            self.server = None
        try:
            self.__dimension = dimension or g.dimension
        except RuntimeError:
            self.__dimension = None
        # if not self._async_operator.is_alive():
        #     self._async_operator.start()

    def set_dimension(self, dm: 'Dimension'):
        if self.__dimension is None:
            self.__dimension = dm

    def set_server(self, server: 'Server'):
        if self.server is None:
            self.server = server

    def create_token(self, destination: Server) -> Token:
        while True:
            tk_id = int(random() * 10000000000000000)
            if not any(getattr(m.token, 'id', None) == tk_id for m in self._mapper):
                return Token(id=tk_id, source=str(self.server.id), destination=str(destination.id))

    def invoke_remote_cmd(self, command: Command, destination: Server, callback: Callback):
        """
        Sends a command to a remote host and executes the command

        Parameters
        ----------
        command:
            command to send
        destination:
            server where command must be executed
        callback:
            function to call when the command completion command comes up

        Returns
        -------

        """
        tkn = self.create_token(destination)
        m = Mapper(applicant=command, destination=destination, token=tkn, callback=callback)
        self._mapper.append(m)

        content = dict()
        content['command'] = command

        response, rc = gtw.send_message(destination=destination, source=self.server,
                                        pub_key=getattr(self.__dimension, 'public', None),
                                        priv_key=getattr(self.__dimension, 'private', None),
                                        data=dict(msg_type=TypeMsg.INVOKE_CMD,
                                                  token=tkn,
                                                  content=content))

    def invoke_local_cmd(self, command: Command, token: Token) -> int:
        """
        Invokes a command. Called from a remote Host

        Parameters
        ----------
        command:
            command to execute.  called from remote host
        token:
            token object

        Returns
        -------
        int
            task id to track
        """
        m = Mapper(applicant=command, token=token)
        self._mapper.append(m)
        with SessionManager(m) as session:
            # save command in case it wants to undo
            session.command = command
            return self._async_operator.register(async_proc=command.invoke, callback=self._send_command_completion,
                                                 callback_kw={'token': token}, name='invoke command')

    def _send_command_completion(self, data, token: Token):
        # print('_send_command_completion')
        content = dict()
        content['data'] = data
        m = self._mapper.get_by('token', token)
        with SessionManager(m) as session:
            content['execution'] = session.command.execution
            ip, port = token.source.split(':')
            source = Server.query.filter_by(ip=ip)

            response, rc = gtw.send_message(destination=source, source=self.server,
                                            pub_key=getattr(self.__dimension, 'public', None),
                                            priv_key=getattr(self.__dimension, 'private', None),
                                            data=dict(msg_type=TypeMsg.COMPLETED_CMD,
                                                      token=token,
                                                      session=session.id,
                                                      content=content))

    def execute_callback(self, data: t.Any, token: Token, session: int) -> None:
        """
        when a message comes up it executes the callback associated with it

        Parameters
        ----------
        data:
            data received from command completion
        token:
            token associated with the original message. Used to get the callback to execute
        session:
            session returned back from server to future calls

        Returns
        -------
        None
        """
        m = self._mapper.get_by('token', token)
        # set token to null
        m.token = None
        m.session = session

        # load callback
        callback = m.callback
        callback_params = inspect.signature(callback[0]).parameters
        if 'data' in callback_params:
            callback[0](*callback[1], data=data, **callback[2])
        else:
            callback[0](*callback[1], **callback[2])

    def undo_remote_command(self, command: Command, callback: Callback) -> None:
        m = self._mapper.get_by('applicant', command)
        m.token = self.create_token(m.destination)
        m.callback = callback
        response, rc = gtw.send_message(destination=m.destination, source=self.server,
                                        pub_key=getattr(self.__dimension, 'public', None),
                                        priv_key=getattr(self.__dimension, 'private', None),
                                        data=dict(msg_type=TypeMsg.UNDO_CMD,
                                                  token=m.token,
                                                  session=m.session))

    def undo_local_command(self, token: Token, session: int) -> None:
        """
        undoes the command
        Parameters
        ----------
        token
        session

        Returns
        -------

        """
        m = self._mapper.get_by('session', session)
        # set the new token to give the response
        m.token = token
        with SessionManager(m) as session:
            # generate callback to send response back to the remote host
            self._async_operator.register(async_proc=session.command.undo, callback=self._send_command_completion,
                                          callback_kw={'token': token})

    def clear(self):
        """
        clears the mapper data
        Returns
        -------
        None
        """
        self._mapper = AttributeFilterList()

    def lock_unlock(self, action: str, scope: Scope, servers: t.List[Server]) -> None:
        """

        Parameters
        ----------
        action
            'U' for unlocking and 'L' for locking
        scope
            scope of the lock
        servers
            servers to ask for a lock

        Raises
        ------
        Raises an error if something went wrong

        Returns
        -------
        None
            returns none if all went as expected.
        """

        assert action in 'UL'

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        tasks = []
        if action == 'U':
            for s in servers:
                tasks.append(gtw.async_send_message(destination=s, source=self.server,
                                                    pub_key=getattr(self.__dimension, 'public', None),
                                                    priv_key=getattr(self.__dimension, 'private', None),
                                                    data=dict(msg_type=TypeMsg.UNLOCK,
                                                              content={'scope': scope,
                                                                       'applicant': str(self.server.id)})))
            pool_responses = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=False))
            if len(servers) == len(list(filter(lambda r: r[1] == 200, pool_responses))):
                return
        else:
            for s in servers:
                tasks.append(
                    gtw.async_send_message(destination=s, source=self.server,
                                           pub_key=getattr(self.__dimension, 'public', None),
                                           priv_key=getattr(self.__dimension, 'private', None),
                                           data=dict(msg_type=TypeMsg.PREVENT_LOCK,
                                                     content={'scope': scope,
                                                              'applicant': str(
                                                                  self.server.id)})))
            pool_responses = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=False))
            if len(servers) == len(list(filter(lambda r: r[1] == 200, pool_responses))):
                tasks = []
                for s in servers:
                    tasks.append(gtw.async_send_message(destination=s, source=self.server,
                                                        pub_key=getattr(self.__dimension, 'public', None),
                                                        priv_key=getattr(self.__dimension, 'private', None),
                                                        data=dict(msg_type=TypeMsg.LOCK,
                                                                  content={'scope': scope,
                                                                           'applicant': str(self.server.id)})))
                pool_responses = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=False))
                if len(servers) == len(list(filter(lambda r: r[1] == 200, pool_responses))):
                    return

        loop.close()

        e = [ue.ErrorServerLock(server=servers[idx], msg=item[0]) for idx, item in enumerate(pool_responses) if
             item[1] != 200]
        raise ue.ErrorLock(errors=e)

    def local_lock_unlock(self, action: str, scope: Scope, applicant: t.Any) -> t.Tuple[bool, t.Any]:
        """

        Parameters
        ----------
        action
            'U' for unlocking, 'P' for preventing lock and 'L' for locking
        scope
            scope of the lock
        applicant
            applicant who requests for the lock

        Returns
        -------
        tuple
        """
        assert action in 'PLU'
        try:
            if action == 'L':
                self._interactor.lockers[scope].lock(applicant)
            elif action == 'U':
                self._interactor.lockers[scope].unlock(applicant)
            else:
                self._interactor.lockers[scope].preventing_lock(self._interactor.lockers, applicant)
        except de.LockerError as e:
            ret = False, e.args[0]
            # ret = False, e
        else:
            ret = True, None
        return ret

    def local_get_delta_catalog(self, data_mark: datetime.datetime) -> t.Dict[str, t.List[Kwargs]]:
        data = {}
        for name, obj in get_distributed_entities():
            c = Catalog.get(name)
            repo_data = obj.query.filter(obj.last_modified_at > data_mark)
            if repo_data:
                data.update({name: repo_data})
        return data

    def remote_get_delta_catalog(self, data_mark: str, server: Server) -> t.Dict[str, t.List[Kwargs]]:
        response, code = gtw.send_message(destination=server, source=self.server,
                                          pub_key=getattr(self.__dimension, 'private', None),
                                          priv_key=getattr(self.__dimension, 'private', None),
                                          data=dict(msg_type=TypeMsg.UPDATE_CATALOG,
                                                    content=data_mark))
        if code == 200:
            return json.loads(response)
        else:
            raise ue.CommunicationError(server, response, code)

    def send_data_log(self, filename: str, server: Server, data_log: t.Union[str, bytes], dest_folder: str):
        if data_log:
            response, code = gtw.send_message(destination=server, source=self.server,
                                              pub_key=getattr(self.__dimension, 'public', None),
                                              priv_key=getattr(self.__dimension, 'private', None),
                                              data=dict(filename=filename,
                                                        data_log=data_log, dest_folder=dest_folder,
                                                        raise_for_status=False))
            if code == 200:
                return response
            else:
                raise ue.CommunicationError(server, response, code)

    def receive_data_log(self, filename: str, data_log: t.Union[str, bytes], dest_folder: str):
        try:
            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder)
            file = os.path.join(dest_folder, filename)

            with open(file, 'ab' if isinstance(data_log, bytes) else 'a') as fh:
                fh.write(data_log)
        except Exception as e:
            return {"error": str(e)}
        return ""
