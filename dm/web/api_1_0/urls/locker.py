import threading

from flask import request, current_app, g
from flask_jwt_extended import jwt_required

from dm import defaults
from dm.domain.entities.locker import Scope, State, Locker
from dm.web import db
from dm.web.api_1_0 import api_bp
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema
from dm.web.json_schemas import schema_lock


def revert_preventing(app, scope, applicant):
    with app.app_context():
        l = Locker.query.with_for_update().get(scope)
        if l.state == State.PREVENTING and l.applicant == applicant:
            l.state = State.UNLOCKED
            l.applicant = None
        db.session.commit()


@api_bp.route('/locker', methods=['GET', 'POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(POST=schema_lock)
def locker():
    if request.method == 'POST':
        json = request.get_json()
        l: Locker = Locker.query.with_for_update().get(Scope[json['scope']])
        current_app.logger.debug(f"Lock request for {json.get('action')} on {json.get('scope')} from {g.source.name}")
        if json['action'] == 'PREVENT':
            # check status from current scope
            if l.state == State.UNLOCKED:
                # check priority
                prioritary_lockers = Locker.query.filter(Locker.priority < l.priority)
                cond = any([pl.state in (State.PREVENTING, State.LOCKED) for pl in prioritary_lockers])
                if not cond:
                    l.state = State.PREVENTING
                    l.applicant = json.get('applicant')
                    th = threading.Timer(defaults.TIMEOUT_PREVENTING_LOCK, revert_preventing,
                                         (current_app._get_current_object(), l.scope, l.applicant))
                    th.daemon = True
                    th.start()
                    db.session.commit()
                    return {'message': 'Preventing lock acquired'}, 200
                else:
                    return {'error': 'Unable to request for lock'}, 409
            else:
                return {'error': 'Unable to request for lock.'}, 409
        elif json['action'] == 'LOCK':
            if l.state == State.PREVENTING and l.applicant == json['applicant']:
                l.state = State.LOCKED
                db.session.commit()
                current_app.logger.debug(f"Lock from {g.source.name} on {l.scope.name} acquired")
                return {'message': 'Locked'}, 200
            else:
                return {'error': 'Unable to lock.'}, 409
        elif json['action'] == 'UNLOCK':
            if (l.state == State.PREVENTING or l.state == State.LOCKED) and l.applicant == json['applicant']:
                l.state = State.UNLOCKED
                l.applicant = None
                db.session.commit()
                current_app.logger.debug(f"Lock on {l.scope.name} released")
                return {'message': 'UnLocked'}, 200
            else:
                return {'error': 'Unable to unlock.'}, 409
