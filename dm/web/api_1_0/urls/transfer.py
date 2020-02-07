import os
import re
from datetime import datetime

import jsonschema
from flask import request, g, current_app
from flask_jwt_extended import jwt_required

from dm.domain.entities import Transfer, Software
from dm.domain.entities.transfer import Status as TransferStatus
from dm.use_cases.interactor import DEFAULT_CHUNK_SIZE
from dm.utils.helpers import md5
from dm.web import db
from dm.web.api_1_0 import api_bp
from dm.web.api_1_0.routes import UUID_pattern, join
from dm.web.decorators import securizer, forward_or_dispatch

schema_transfers = {
    "type": "object",
    "properties": {
        "software_id": {"type": "string",
                        "pattern": UUID_pattern},
        "dest_path": {"type": "string"},
        "filename": {"type": "string"},
        "num_chunks": {"type": "integer",
                       "minimum": 0}
    },
    "required": ["software_id"]
}
TEMPORAL_DIRECTORY = '.tmp'


@api_bp.route('/transfers/', methods=['GET', 'POST'])
@securizer
@jwt_required
@forward_or_dispatch
def transfers():
    if request.method == 'GET':
        return [t.to_json() for t in Transfer.query.all()]
    elif request.method == 'POST':
        # validation
        json = request.get_json()
        jsonschema.validate(json, schema_transfers)
        soft = Software.query.get(json['software_id'])
        if not soft:
            return {"error": f"Software id '{json['software_id']}' not found"}, 404

        t = Transfer(software=soft, dest_path=json.get('dest_path', current_app.config['SOFTWARE_DIR']),
                     filename=json.get('filename', soft.filename),
                     num_chunks=json.get('num_chunks'))

        if not os.path.exists(t.dest_path):
            os.makedirs(t.dest_path)
        tmp = os.path.join(t.dest_path, TEMPORAL_DIRECTORY)
        if not os.path.exists(tmp):
            os.mkdir(tmp)

        db.session.add(t)
        db.session.commit()
        return {'transfer_id': str(t.id)}, 202


schema_transfer = {
    "type": "object",
    "properties": {
        "transfer_id": {"type": "string",
                        "pattern": UUID_pattern},
        "chunk": {"type": "integer",
                  "minimum": 0},
        "content": {"type": "bytes"},
    },
    "required": ["transfer_id", "chunk", "content"]
}
CHUNK_READ_BUFFER = DEFAULT_CHUNK_SIZE


@api_bp.route('/transfers/<transfer_id>', methods=['GET', 'POST', 'PATCH'])
@securizer
@jwt_required
@forward_or_dispatch
def transfer(transfer_id):
    if request.method == 'GET':
        trans = Transfer.query.get(transfer_id)
        if not trans:
            return {"error": f"transfer id '{transfer_id}' not found"}, 404
        else:
            return trans.to_json()
    elif request.method == 'POST':
        """Generates the chunk into disk"""
        trans: Transfer = Transfer.query.get(transfer_id)
        if trans is None:
            return {"error": f"transfer id '{transfer_id}' not found"}, 404
        if trans.status == TransferStatus.WAITING_CHUNKS:
            trans.started_on = datetime.now()
            trans.status = TransferStatus.IN_PROGRESS
            db.session.commit()
        chunk = g.unpacked_data.get('chunk_content')
        chunk_id = g.unpacked_data.get('chunk')
        with open(os.path.join(trans.dest_path, TEMPORAL_DIRECTORY, f'chunk.{chunk_id}'), 'wb') as fd:
            fd.write(chunk)
        return '', 201
    elif request.method == 'PATCH':
        "ends the transfer creating the file"
        trans: Transfer = Transfer.query.get(transfer_id)
        if trans is None:
            return {"error": f"transfer id '{transfer_id}' not found"}, 404
        path = os.path.join(trans.dest_path, TEMPORAL_DIRECTORY)
        chunk_pattern = re.compile(r"^chunk\.(\d+)$")
        file = os.path.join(trans.dest_path, trans.filename)
        files, chunks_ids = zip(*sorted(
            [(f, int(chunk_pattern.match(f).groups()[0])) for f in os.listdir(path) if
             os.path.isfile(os.path.join(path, f)) and chunk_pattern.match(f)],
            key=lambda x: x[1]))

        if len(files) != trans.num_chunks or sum(chunks_ids) != (trans.num_chunks - 1) * trans.num_chunks / 2:
            return {"error": f"Not enough chunks to generate file"}, 404
        with open(file, 'wb') as outfile:
            for fname in files:
                with open(os.path.join(path, fname), 'rb') as infile:
                    while True:
                        c = infile.read(CHUNK_READ_BUFFER)
                        if not c:
                            break
                        outfile.write(c)
        # check final file length and checksum
        if os.path.getsize(file) != trans.software.size_bytes:
            trans.status = TransferStatus.SIZE_ERROR
            db.session.commit()
            # os.remove(file)
            return {"error": f"Error on transfer '{transfer_id}': Final file size does not match expected size"}, 404

        if md5(file) != trans.software.checksum:
            trans.status = TransferStatus.CHECKSUM_ERROR
            db.session.commit()
            # os.remove(file)
            return {"error": f"Error on transfer '{transfer_id}': Checksum error"}, 404

        trans.status = TransferStatus.COMPLETED
        db.session.commit()
        return '', 204
