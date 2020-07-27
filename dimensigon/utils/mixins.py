from dimensigon.utils.helpers import get_logger


class LoggerMixin:
    @property
    def logger(self):
        return get_logger(self)
