import logging
import multiprocessing as mp
import threading
from datetime import datetime

from flask import request, current_app, g, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import OperationalError

from dimensigon import defaults
from dimensigon.domain.entities import Catalog
from dimensigon.domain.entities.locker import Scope, State, Locker
from dimensigon.web import db, errors
from dimensigon.web.api_1_0 import api_bp
from dimensigon.web.decorators import securizer, forward_or_dispatch, validate_schema
from dimensigon.web.helpers import transaction
from dimensigon.web.json_schemas import locker_prevent_post, locker_unlock_lock_post

logger = logging.getLogger('dm.lock')


@api_bp.route('/locker', methods=['GET'])
@forward_or_dispatch()
@jwt_required
@securizer
def locker():
    data = []
    for l in Locker.query.all():
        data.append({l.scope.name: l.state.name})
    return jsonify(data), 200


def revert_preventing(app, scope, applicant):
    with app.app_context():
        try:
            l = Locker.query.with_for_update().get(scope)
            if l.state == State.PREVENTING and l.applicant == applicant:
                l.state = State.UNLOCKED
                l.applicant = None

            db.session.commit()
        except OperationalError as e:
            db.session.rollback()


@api_bp.route('/locker/prevent', methods=['POST'])
@forward_or_dispatch()
@jwt_required
@securizer
@validate_schema(POST=locker_prevent_post)
def locker_prevent():
    json_data = request.get_json()
    l: Locker = Locker.query.get(Scope[json_data['scope']])
    logger.debug(f"PreventLock requested on {json_data.get('scope')} from {g.source}")

    # when orchestration scope check if applicant is the same as the current
    if l.scope == Scope.ORCHESTRATION \
            and l.state in (State.PREVENTING, State.LOCKED) \
            and l.applicant == json_data.get('applicant'):
        return {'message': f"{l.scope.name} already in {l.state.name} state"}, 210
    elif l.scope == Scope.UPGRADE and l.state in (State.PREVENTING, State.LOCKED):
        return {'message': f"{l.scope.name} already in {l.state.name} state"}, 210

    # check status from current scope
    if l.state == State.UNLOCKED:
        # check priority
        prioritary_lockers = Locker.query.filter(Locker.scope != l.scope).all()
        prioritary_lockers = [pl for pl in prioritary_lockers if pl.scope < l.scope]
        cond = any([pl.state in (State.PREVENTING, State.LOCKED) for pl in prioritary_lockers])
        if not cond:
            # catalog serialization
            if json_data['scope'] != Scope.UPGRADE.name:
                datemark = datetime.strptime(json_data['datemark'], defaults.DATEMARK_FORMAT)
                catalog_ver = Catalog.max_catalog()
                if datemark < catalog_ver:
                    raise errors.ObsoleteCatalog(catalog_ver, datemark)
            with transaction():
                l.state = State.PREVENTING
                l.applicant = json_data.get('applicant')
            th = threading.Timer(defaults.TIMEOUT_PREVENTING_LOCK, revert_preventing,
                                 (current_app._get_current_object(), l.scope, l.applicant))
            th.daemon = True
            th.start()
            return {json_data['scope']: 'PREVENTING'}, 200
        else:
            raise errors.PriorityLocker(l.scope)
    else:
        raise errors.StatusLockerError(l.scope, 'P', l.state)


counter = mp.Value('i', 0)


@api_bp.route('/locker/lock', methods=['POST'])
@forward_or_dispatch()
@jwt_required
@securizer
@validate_schema(POST=locker_unlock_lock_post)
def locker_lock():
    json_data = request.get_json()
    l: Locker = Locker.query.get(Scope[json_data['scope']])
    logger.debug(f"Lock requested on {json_data.get('scope')} from {g.source}")

    if Scope[json_data['scope']] == Scope.ORCHESTRATION \
            and l.state == State.LOCKED \
            and l.applicant == json_data.get('applicant'):
        return {'message': f"{json_data['scope']} already in {l.state} state"}, 210
    elif l.scope == Scope.UPGRADE and l.state == State.LOCKED:
        with counter.get_lock():
            counter.value += 1
        return {'message': f"{l.scope.name} already in {l.state.name} state"}, 210

    if l.state == State.PREVENTING:
        if l.applicant == json_data['applicant']:
            with transaction():
                l.state = State.LOCKED
            if l.scope == Scope.UPGRADE:
                with counter.get_lock():
                    counter.value += 1
            logger.debug(f"Lock from {g.source} on {l.scope.name} acquired")
            return {json_data['scope']: 'LOCKED'}, 200
        else:
            raise errors.ApplicantLockerError(l.scope)
    else:
        raise errors.StatusLockerError(l.scope, 'L', l.state)


@api_bp.route('/locker/unlock', methods=['POST'])
@forward_or_dispatch()
@jwt_required
@securizer
@validate_schema(POST=locker_unlock_lock_post)
def locker_unlock():
    json_data = request.get_json()
    l: Locker = Locker.query.get(Scope[json_data['scope']])
    logger.debug(f"Unlock requested on {json_data.get('scope')} from {g.source}")

    if 'force' in json_data and json_data['force']:
        if get_jwt_identity() != '00000000-0000-0000-0000-000000000001':
            raise errors.UserForbiddenError()
        else:
            with transaction():
                l.state = State.UNLOCKED
                l.applicant = None
            if l.scope == Scope.UPGRADE:
                with counter.get_lock():
                    counter.value = 0
            return {json_data['scope']: 'UNLOCKED'}, 200

    if l.scope == Scope.ORCHESTRATION and l.state == State.UNLOCKED:
        return {'message': f"{json_data['scope']} already in {l.state} state"}, 210
    elif l.scope == Scope.UPGRADE and l.state == State.LOCKED:
        with counter.get_lock():
            counter.value -= 1
            if counter.value == 0:
                with transaction():
                    l.state = State.UNLOCKED
                    l.applicant = None
                logger.debug(f"Lock on {l.scope.name} released")
                return {json_data['scope']: 'UNLOCKED'}, 200
            else:
                return {'message': 'Pending upgrades'}, 210
    elif l.state == State.PREVENTING or l.state == State.LOCKED:
        if l.applicant == json_data['applicant']:
            with transaction():
                l.state = State.UNLOCKED
                l.applicant = None
            logger.debug(f"Lock on {l.scope.name} released")
            return {json_data['scope']: 'UNLOCKED'}, 200
        else:
            raise errors.ApplicantLockerError(l.scope)
    else:
        raise errors.StatusLockerError(l.scope, 'U', l.state)
