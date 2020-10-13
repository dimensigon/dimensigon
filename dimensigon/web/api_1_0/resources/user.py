from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities.user import User
from dimensigon.web import db
from dimensigon.web.decorators import forward_or_dispatch, securizer, validate_schema, lock_catalog
from dimensigon.web.helpers import filter_query
from dimensigon.web.json_schemas import users_post, user_patch


class UserList(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(User, request.args, exclude=['_password'])
        return [user.to_json() for user in query.all()]

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(users_post)
    @lock_catalog
    def post(self):
        data = request.get_json()
        password = data.pop("password")
        u = User(**data)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return {'id': str(u.id)}, 201


class UserResource(Resource):
    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, user_id):
        return User.query.get_or_raise(user_id).to_json()

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(user_patch)
    @lock_catalog
    def patch(self, user_id):
        user = User.query.get_or_raise(user_id)
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
    # @jwt_required
    # @forward_or_dispatch()
    # def delete(self, user_id):
    #     user = User.query.get_or_raise(user_id)
    #     db.session.delete(user)
    #     db.session.commit()
    #     return {}, 204
