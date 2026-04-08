from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_restful import Resource
from sqlalchemy import distinct, select

from dimensigon.domain.entities import Vault
from dimensigon.web import errors, db
from dimensigon.web.decorators import forward_or_dispatch, securizer, lock_catalog, validate_schema
from dimensigon.web.helpers import filter_query, check_param_in_uri, get_or_raise
from dimensigon.web.json_schemas import vault_post, vaults_post, vault_put


class VaultList(Resource):

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self):
        if check_param_in_uri('scopes'):
            stmt = select(distinct(Vault.scope)).where(
                Vault.user_id == get_jwt_identity(), Vault.deleted == False
            )
            return [r[0] for r in db.session.execute(stmt).all()]
        elif check_param_in_uri('vars'):
            stmt = select(distinct(Vault.name)).where(
                Vault.user_id == get_jwt_identity(), Vault.deleted == False
            )
            if 'scope' in request.args:
                stmt = stmt.where(Vault.scope == request.args.get('scope'))
            stmt = stmt.order_by(Vault.name)
            return [r[0] for r in db.session.execute(stmt).all()]
        else:
            stmt = filter_query(Vault, request.args, exclude=["user_id", "value"]).where(
                Vault.user_id == get_jwt_identity())
            return [vault.to_json(no_delete=True, human=check_param_in_uri('human')) for vault in db.session.execute(stmt).scalars().all()]

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @validate_schema(vaults_post)
    @lock_catalog
    def post(self):
        data = request.get_json()
        v = db.session.get(Vault, (get_jwt_identity(), data.get('scope', 'global'), data['name']))
        if v:
            raise errors.EntityAlreadyExists("Vault", (data.get('scope', 'global'), data['name']), ("scope", "name"))

        v = Vault(user_id=get_jwt_identity(), scope=data.get('scope', 'global'), name=data['name'], value=data['value'])
        db.session.add(v)
        db.session.commit()
        return {}, 204


class VaultResource(Resource):

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self, name, scope='global'):
        return get_or_raise(Vault, (get_jwt_identity(), scope, name)).to_json(human=check_param_in_uri('human'),
                                                                              no_delete=True)

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @validate_schema(vault_post)
    @lock_catalog
    def post(self, name, scope='global'):
        data = request.get_json()
        v = get_or_raise(Vault, (get_jwt_identity(), scope, name))

        v.value = data['value']
        db.session.commit()
        return {}, 204

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @validate_schema(vault_put)
    @lock_catalog
    def put(self, name, scope='global'):
        data = request.get_json()
        v = db.session.get(Vault, (get_jwt_identity(), scope, name))
        if v is None:
            v = Vault(user_id=get_jwt_identity(), scope=scope, name=name)
            db.session.add(v)
        v.value = data['value']
        db.session.commit()
        return {}, 204

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @lock_catalog
    def delete(self, name, scope='global'):
        v = get_or_raise(Vault, (get_jwt_identity(), scope, name))
        v.delete()
        db.session.commit()
        return {}, 204
