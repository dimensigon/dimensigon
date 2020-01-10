from datetime import datetime

from sqlalchemy import DateTime, Column


class DistributedEntityMixin:
    last_modified_at = Column(DateTime, nullable=False)

    def __init__(self, **kwargs):
        self.last_modified_at = kwargs.pop('last_modified_at', None)