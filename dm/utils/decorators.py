from dm.utils.helpers import get_logger


def logged(klass):
    klass.logger = get_logger(klass)
    return klass



