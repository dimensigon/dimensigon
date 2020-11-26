from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_restful import Resource
from sqlalchemy import distinct

from dimensigon.domain.entities import Vault
from dimensigon.web import errors, db
from dimensigon.web.decorators import forward_or_dispatch, securizer, lock_catalog, validate_schema
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import vault_post, vaults_post, vault_put


class VaultList(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self):
        if check_param_in_uri('scopes'):
            return [r[0] for r in
                    Vault.query.filter_by(user_id=get_jwt_identity()).filter_by(deleted=0).order_by(Vault.scope)]
        elif check_param_in_uri('vars'):
            query = db.session.query(distinct(Vault.name)).filter_by(user_id=get_jwt_identity()).filter_by(deleted=0)
            if 'scope' in request.args:
                query = query.filter_by(scope=request.args.get('scope'))
            return [r[0] for r in query.order_by(Vault.name)]
        else:
            query = filter_query(Vault, request.args, exclude=["user_id", "value"]).filter_by(
                user_id=get_jwt_identity())
            return [vault.to_json(no_delete=True) for vault in query.all()]

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(vaults_post)
    @lock_catalog
    def post(self):
        data = request.get_json()
        v = Vault.query.get((get_jwt_identity(), data.get('scope', 'global'), data['name']))
        if v:
            raise errors.EntityAlreadyExists("Vault", (data.get('scope', 'global'), data['name']), ("scope", "name"))

        v = Vault(user_id=get_jwt_identity(), scope=data.get('scope', 'global'), name=data['name'], value=data['value'])
        db.session.add(v)
        db.session.commit()
        return {}, 204


class VaultResource(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, name, scope='global'):
        return Vault.query.get_or_raise((get_jwt_identity(), scope, name)).to_json(human=check_param_in_uri('human'),
                                                                                   no_delete=True)

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(vault_post)
    @lock_catalog
    def post(self, name, scope='global'):
        data = request.get_json()
        v = Vault.query.get_or_raise((get_jwt_identity(), scope, name))

        v.value = data['value']
        db.session.commit()
        return {}, 204

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(vault_put)
    @lock_catalog
    def put(self, name, scope='global'):
        data = request.get_json()
        v = Vault.query.get((get_jwt_identity(), scope, name))
        if v is None:
            v = Vault(user_id=get_jwt_identity(), scope=scope, name=name)
            db.session.add(v)
        v.value = data['value']
        db.session.commit()
        return {}, 204

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @lock_catalog
    def delete(self, name, scope='global'):
        v = Vault.query.get_or_raise((get_jwt_identity(), scope, name))
        v.delete()
        db.session.commit()
        return {}, 204
