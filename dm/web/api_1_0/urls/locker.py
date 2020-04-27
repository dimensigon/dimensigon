import threading
from datetime import datetime

from flask import request, current_app, g
from flask_jwt_extended import jwt_required

from dm import defaults
from dm.domain.entities import Catalog
from dm.domain.entities.locker import Scope, State, Locker
from dm.web import db
from dm.web.api_1_0 import api_bp
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema
from dm.web.json_schemas import locker_prevent_post, locker_unlock_lock_post


def revert_preventing(app, scope, applicant):
    with app.app_context():
        l = Locker.query.with_for_update().get(scope)
        if l.state == State.PREVENTING and l.applicant == applicant:
            l.state = State.UNLOCKED
            l.applicant = None
        db.session.commit()


@api_bp.route('/locker/prevent', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(POST=locker_prevent_post)
def locker_prevent():
    json_data = request.get_json()
    l: Locker = Locker.query.with_for_update().get(Scope[json_data['scope']])
    current_app.logger.debug(f"PreventLock requested on {json_data.get('scope')} from {g.source}")

    # check status from current scope
    if l.state == State.UNLOCKED:
        # check priority
        prioritary_lockers = Locker.query.filter_by(Locker.scope != l.scope).all()
        prioritary_lockers = [pl for pl in prioritary_lockers if pl.scope < l.scope]
        cond = any([pl.state in (State.PREVENTING, State.LOCKED) for pl in prioritary_lockers])
        if not cond:
            # catalog serialization
            if json_data['scope'] != Scope.UPGRADE.name:
                datemark = datetime.strptime(json_data['datemark'], defaults.DATEMARK_FORMAT)
                catalog_ver = Catalog.max_catalog()
                if datemark < catalog_ver:
                    return {"error": f"Old catalog datemark. "
                                     f"Upgrade Catalog to {catalog_ver.strftime(defaults.DATEMARK_FORMAT)} to lock"
                            }, 409
            l.state = State.PREVENTING
            l.applicant = json_data.get('applicant')
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


@api_bp.route('/locker/lock', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(POST=locker_unlock_lock_post)
def locker_lock():
    json_data = request.get_json()
    l: Locker = Locker.query.with_for_update().get(Scope[json_data['scope']])
    current_app.logger.debug(f"Lock requested on {json_data.get('scope')} from {g.source}")
    if l.state == State.PREVENTING and l.applicant == json_data['applicant']:
        l.state = State.LOCKED
        db.session.commit()
        current_app.logger.debug(f"Lock from {g.source} on {l.scope.name} acquired")
        return {'message': 'Locked'}, 200
    else:
        return {'error': 'Unable to lock.'}, 409


@api_bp.route('/locker/unlock', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(POST=locker_unlock_lock_post)
def locker_unlock():
    json_data = request.get_json()
    l: Locker = Locker.query.with_for_update().get(Scope[json_data['scope']])
    current_app.logger.debug(f"Unlock requested on {json_data.get('scope')} from {g.source}")
    if (l.state == State.PREVENTING or l.state == State.LOCKED) and l.applicant == json_data['applicant']:
        l.state = State.UNLOCKED
        l.applicant = None
        db.session.commit()
        current_app.logger.debug(f"Lock on {l.scope.name} released")
        return {'message': 'UnLocked'}, 200
    else:
        return {'error': 'Unable to unlock.'}, 409
