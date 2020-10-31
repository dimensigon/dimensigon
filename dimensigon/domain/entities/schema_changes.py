from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import UtcDateTime
from dimensigon.web import db


class SchemaChanges(db.Model):
    """Representation of schema version changes."""

    __tablename__ = "L_schema_changes"
    change_id = db.Column(db.Integer, primary_key=True)
    schema_version = db.Column(db.Integer)
    changed = db.Column(UtcDateTime(timezone=True), default=get_now)

    @staticmethod
    def set_initial(session=None):
        from dimensigon.domain.entities import SCHEMA_VERSION
        count = session.query(SchemaChanges).count()
        # database started
        if count == 0:
            sc = SchemaChanges(schema_version=SCHEMA_VERSION)
            db.session.add(sc)
