import base64
import functools

import rsa
from flask import g, current_app
from flask import request
from flask import session, url_for

from dm.domain.entities import Server
from dm.network.gateway import unpack_msg, pack_msg
from dm.utils.helpers import get_logger


def logged(klass):
    klass.logger = get_logger(klass)
    return klass



