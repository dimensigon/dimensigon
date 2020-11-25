import time


class EventMessage:
    __slots__ = ('__id', '__event_type', '__source', 'args', 'kwargs')

    def __init__(self, __event_type: str, *args, source: str = None, **kwargs):
        self.__id = time.time()
        self.__event_type = __event_type
        self.__source = source
        self.args = tuple(args)
        self.kwargs = kwargs

    @property
    def id(self):
        return self.__id

    @property
    def event_type(self):
        return self.__event_type

    @property
    def source(self):
        return self.__source

    def __str__(self):
        s = ""
        if self.__source:
            s += f"{self.__source}-"
        s += f"{self.__event_type}("
        if self.args:
            s += str(self.args)[1:-1]
        if self.kwargs:
            s += ', ' + str(self.kwargs)[1:-1]
        s += ')'
        return s

    def __repr__(self):
        return str(self)


class BaseEvent(EventMessage):

    def __init__(self, *args, source: str = None, **kwargs):
        super().__init__(self.__class__.__name__, *args, source=source, **kwargs)


class Stop(BaseEvent):
    """Event to stop the program"""


class StopEventHandler(BaseEvent):
    """Event to stop """
