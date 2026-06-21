from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_restful import Resource
from sqlalchemy import select

from dimensigon.domain.entities.user import User
from dimensigon.web import db, errors
from dimensigon.web.admin.auth import get_user_role_level, ROLE_HIERARCHY
from dimensigon.web.decorators import forward_or_dispatch, securizer, validate_schema, lock_catalog
from dimensigon.web.helpers import filter_query, get_or_raise
from dimensigon.web.json_schemas import users_post, user_patch


def _current_user():
    return db.session.get(User, get_jwt_identity())


def _require_administrator():
    """Fail-closed administrator check for user-management endpoints."""
    user = _current_user()
    if not user or get_user_role_level(user) < ROLE_HIERARCHY['administrator']:
        raise errors.UserForbiddenError()
    return user


class UserList(Resource):

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self):
        stmt = filter_query(User, request.args, exclude=['_password'])
        return [user.to_json() for user in db.session.execute(stmt).scalars().all()]

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @validate_schema(users_post)
    @lock_catalog
    def post(self):
        _require_administrator()
        data = request.get_json()
        password = data.pop("password")
        if db.session.execute(select(User).where(User.name == data['name'])).scalars().all():
            raise errors.EntityAlreadyExists("User", data['name'], ['name'])
        u = User(**data)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return {'id': str(u.id)}, 201


class UserResource(Resource):
    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self, user_id):
        return get_or_raise(User, user_id).to_json()

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @validate_schema(user_patch)
    @lock_catalog
    def patch(self, user_id):
        user = get_or_raise(User, user_id)
        # Authorization: only an administrator, or the target user editing their
        # own account, may modify a user record (fail-closed).
        caller = _current_user()
        is_admin = bool(caller) and get_user_role_level(caller) >= ROLE_HIERARCHY['administrator']
        is_self = bool(caller) and str(caller.id) == str(user.id)
        if not (is_admin or is_self):
            raise errors.UserForbiddenError()
        data = request.get_json()
        if 'email' in data and user.email != data.get('email'):
            user.email = data.get('email')
        if 'active' in data and user.active != data.get('active'):
            user.active = data.get('active')
        if user in db.session.dirty:
            db.session.commit()
            return {}, 204
        return {}, 202

    # @securizer
    # @jwt_required()
    # @forward_or_dispatch()
    # def delete(self, user_id):
    #     user = User.query.get_or_raise(user_id)
    #     db.session.delete(user)
    #     db.session.commit()
    #     return {}, 204
