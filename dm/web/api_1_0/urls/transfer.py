import base64
import os
import re
from datetime import datetime

from flask import request, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy import and_

import dm.defaults as d
from dm.domain.entities import Transfer, Software
from dm.domain.entities.transfer import Status as TransferStatus
from dm.utils.helpers import md5
from dm.web import db
from dm.web.api_1_0 import api_bp
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema
from dm.web.json_schemas import schema_transfers


@api_bp.route('/transfers/', methods=['GET', 'POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(POST=schema_transfers)
def transfers():
    if request.method == 'GET':
        return [t.to_json() for t in Transfer.query.all()]
    elif request.method == 'POST':
        # validation
        data = request.get_json()
        soft = Software.query.get(data['software_id'])
        if not soft:
            return {"error": f"Software id '{data['software_id']}' not found"}, 404

        pending = Transfer.query.filter_by(software=soft).filter(
            and_(Transfer.status != TransferStatus.WAITING_CHUNKS,
                 Transfer.status != TransferStatus.IN_PROGRESS)).count()

        if pending > 0:
            return {"error": f"There is already a transfer sending software {soft.id}"}, 400

        dest_path = data.get('dest_path', current_app.config['SOFTWARE_REPO'])
        file = os.path.join(dest_path, soft.filename)

        if not data.get('force', False):
            if os.path.exists(file):
                return {"error": "file already exists"}, 409

        if os.path.exists(file):
            current_app.logger.debug(f'removing file {file}')
            os.remove(file)

        # remove chunk files if exist
        for dirpath, dirnames, filenames in os.walk(dest_path):
            for f in filenames:
                if re.search(rf"^{f}_chunk\.(\d+)$", f):
                    current_app.logger.debug(f'removing chunk file {os.path.join(dest_path, f)}')
                    os.remove(os.path.join(dest_path, f))

        t = Transfer(software=soft, dest_path=dest_path,
                     num_chunks=data.get('num_chunks'))

        if not os.path.exists(t.dest_path):
            os.makedirs(t.dest_path)

        db.session.add(t)
        db.session.commit()
        return {'transfer_id': str(t.id)}, 202


CHUNK_READ_BUFFER = d.CHUNK_SIZE


@api_bp.route('/transfers/<transfer_id>', methods=['GET', 'POST', 'PATCH'])
@forward_or_dispatch
@jwt_required
@securizer
def transfer(transfer_id):
    if request.method == 'GET':
        trans = Transfer.query.get(transfer_id)
        if not trans:
            return {"error": f"transfer id '{transfer_id}' not found"}, 404
        else:
            return trans.to_json()
    elif request.method == 'POST':
        """Generates the chunk into disk"""
        data = request.get_json()
        trans: Transfer = Transfer.query.get(transfer_id)
        if trans is None:
            return {"error": f"transfer id '{transfer_id}' not found"}, 404
        if trans.status == TransferStatus.WAITING_CHUNKS:
            trans.started_on = datetime.now()
            trans.status = TransferStatus.IN_PROGRESS
            db.session.commit()
        chunk = data.get('content')
        chunk_id = data.get('chunk')
        with open(os.path.join(trans.dest_path, f'{trans.software.filename}_chunk.{chunk_id}'), 'wb') as fd:
            raw = base64.b64decode(chunk.encode('ascii'))
            fd.write(raw)
        msg = f"Chunk {chunk_id} from transfer {transfer_id} generated succesfully"
        current_app.logger.debug(msg)
        return {'message': msg}, 201
    elif request.method == 'PATCH':
        """ends the transfer creating the file"""
        trans: Transfer = Transfer.query.get(transfer_id)
        if trans is None:
            return {"error": f"transfer id '{transfer_id}' not found"}, 404
        current_app.logger.debug(
            f"Generating file {os.path.join(trans.dest_path, trans.software.filename)} from transfer {trans.id}")
        chunk_pattern = re.compile(rf"^{trans.software.filename}_chunk\.(\d+)$")
        file = os.path.join(trans.dest_path, trans.software.filename)
        files, chunks_ids = zip(*sorted(
            [(f, int(chunk_pattern.match(f).groups()[0])) for f in os.listdir(trans.dest_path) if
             os.path.isfile(os.path.join(trans.dest_path, f)) and chunk_pattern.match(f)],
            key=lambda x: x[1]))

        if len(files) != trans.num_chunks or sum(chunks_ids) != (trans.num_chunks - 1) * trans.num_chunks / 2:
            msg = f"Not enough chunks to generate file"
            current_app.logger.error(msg)
            return {"error": msg}, 404
        with open(file, 'wb') as outfile:
            for fname in files:
                f = os.path.join(trans.dest_path, fname)
                with open(f, 'rb') as infile:
                    while True:
                        c = infile.read(CHUNK_READ_BUFFER)
                        if not c:
                            break
                        outfile.write(c)
                try:
                    os.remove(f)
                except Exception as e:
                    current_app.logger.warning(f"Unable to remove chunk file {f}. Exception: {e}")
        # check final file length and checksum
        if os.path.getsize(file) != trans.software.size:
            trans.status = TransferStatus.SIZE_ERROR
            db.session.commit()
            # os.remove(file)
            msg = f"Error on transfer '{transfer_id}': Final file size does not match expected size"
            current_app.logger.error(msg)
            return {"error": msg}, 404

        if md5(file) != trans.software.checksum:
            trans.status = TransferStatus.CHECKSUM_ERROR
            db.session.commit()
            # os.remove(file)
            msg = f"Error on transfer '{transfer_id}': Checksum error"
            current_app.logger.error(msg)
            return {"error": msg}, 404

        trans.status = TransferStatus.COMPLETED
        db.session.commit()
        msg = f"File {os.path.join(trans.dest_path, trans.software.filename)} from transfer {trans.id} recived succesfully"
        current_app.logger.debug(msg)
        return {'message': msg}, 204
