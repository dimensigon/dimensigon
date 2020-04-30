from dm.domain.entities import Scope, ActionType

UUID_pattern = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

schema_healthcheck = {
    "type": "object",
    "properties": {
        "action": {"type": "string",
                   "pattern": "^(reboot|stop|software)"},
    },
    "required": ["action"],
}

locker_prevent_post = {
    "type": "object",
    "properties": {
        "scope": {"type": "string",
                  "pattern": f"^({'|'.join([s.name for s in Scope])})$"},
        "applicant": {"type": ["object", "array", "string"]},
        "datemark": {"type": "string"},
    },
    "required": ["scope", "applicant", "datemark"],
    "additionalProperties": False
}

locker_unlock_lock_post = {
    "type": "object",
    "properties": {
        "scope": {"type": "string",
                  "pattern": f"^({'|'.join([s.name for s in Scope])})$"},
        "applicant": {"type": ["object", "array", "string"]},
    },
    "required": ["scope", "applicant"],
    "additionalProperties": False
}


schema_software_send = {
    "type": "object",
    "properties": {
        "software_id": {"type": "string",
                        "pattern": UUID_pattern},
        "dest_server_id": {"type": "string",
                           "pattern": UUID_pattern},
        "dest_path": {"type": "string"},
        "chunk_size": {"type": "integer",
                       # "minimum": 1024 * 1024 * 2,
                       "maximum": 1024 * 1024 * 500,
                       # "multipleOf": 1024
                       },
        "max_senders": {"type": "integer",
                        "minimum": 0}
    },
    "required": ["software_id", "dest_server_id", "dest_path"],
    "additionalProperties": False
}

post_software_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "family": {"type": "string"},
        "server_id": {"type": "string",
                      "pattern": UUID_pattern},
        "file": {"type": "string"}
    },
    "required": ["name", "version", "server_id", "file"],
    "dependencies": {
        "server_id": ["file"],
        "file": ["server_id"],
    },
    "additionalProperties": False
}

patch_software_schema = {
    "type": "object",
    "properties": {
        "server_id": {"type": "string",
                      "pattern": UUID_pattern},
        "path": {"type": "string"},
    },
    "required": ["server_id", "path"],
    "additionalProperties": False
}

put_software_servers_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "server_id": {"type": "string",
                          "pattern": UUID_pattern},
            "file": {"type": "string"}
        },
        "required": ["server_id", "path"]
    },
    "additionalProperties": False
}

post_action_template_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "integer",
                    "minimum": 1},
        "action_type": {"type": "string",
                        "pattern": f"^({'|'.join([at.name for at in ActionType])})$"},
        "code": {"type": "string"},
        "parameters": {"type": "object"},
        "expected_output": {"type": "string"},
        "expected_rc": {"type": "string"},
        "system_kwargs": {"type": "object"},
    },
    "required": ["name", "version", "action_type", "code"],
    "additionalProperties": False
}

_step_post = {
    "type": "object",
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "orchestration_id": {"type": "string",
                             "pattern": UUID_pattern},
        "undo": {"type": "boolean"},
        "action_template_id": {"type": "string",
                               "pattern": UUID_pattern},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"},
        "expected_stdout": {"type": "string"},
        "expected_stderr": {"type": "string"},
        "expected_rc": {"type": "integer"},
        "parameters": {"type": "object"},
        "system_kwargs": {"type": "object"},
        "parent_step_ids": {"type": "array",
                            "items": {"anyOf": [{"type": "string", "pattern": UUID_pattern},
                                                {"type": "integer", "minimum": 1}]
                                      }
                            },
        "child_step_ids": {"type": "array",
                           "items": {"anyOf": [{"type": "string", "pattern": UUID_pattern},
                                               {"type": "integer", "minimum": 1}]
                                     }
                           },
        "target": {"anyOf": [{"type": "string"},
                             {"type": "array", "items": {"type": "string"}}]}
    },
    "required": ["orchestration_id", "undo", "action_template_id"],
    "additionalProperties": False
}

step_post = {
    "anyOf": [
        {"type": "array",
         "items": _step_post},
        _step_post
    ]
}

step_put = {
    "type": "object",
    "properties": {
        "undo": {"type": "boolean"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"},
        "action_template_id": {"type": "string",
                               "pattern": UUID_pattern},
        "expected_stdout": {"type": "string"},
        "expected_stderr": {"type": "string"},
        "expected_rc": {"type": "integer"},
        "parameters": {"type": "object"},
        "system_kwargs": {"type": "object"},
        "parent_step_ids": {"type": "array",
                            "items": {"anyOf": [{"type": "string", "pattern": UUID_pattern},
                                                {"type": "integer", "minimum": 1}]
                                      }
                            },
        "child_step_ids": {"type": "array",
                           "items": {"anyOf": [{"type": "string", "pattern": UUID_pattern},
                                               {"type": "integer", "minimum": 1}]
                                     }
                           },
        "target": {"anyOf": [{"type": "string"},
                             {"type": "array", "items": {"type": "string"}}]}
    },
    "required": ["undo", "action_template_id"],
    "additionalProperties": False
}

step_patch = {
    "type": "object",
    "properties": {
        "undo": {"type": "boolean"},
        "action_template_id": {"type": "string",
                               "pattern": UUID_pattern},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"},
        "expected_stdout": {"type": "string"},
        "expected_stderr": {"type": "string"},
        "expected_rc": {"type": "integer"},
        "parameters": {"type": "object"},
        "system_kwargs": {"type": "object"},
        "parent_step_ids": {"type": "array",
                            "items": {"anyOf": [{"type": "string", "pattern": UUID_pattern},
                                                {"type": "integer", "minimum": 1}]
                                      }
                            },
        "child_step_ids": {"type": "array",
                           "items": {"anyOf": [{"type": "string", "pattern": UUID_pattern},
                                               {"type": "integer", "minimum": 1}]
                                     }
                           },
        "target": {"anyOf": [{"type": "string"},
                             {"type": "array", "items": {"type": "string"}}]}
    },
    "additionalProperties": False
}

step_parents = {
    "type": "object",
    "properties": {
        "parent_step_ids": {"type": "array", "items": {"type": "string", "pattern": UUID_pattern}},
        "additionalProperties": False
    }
}

step_children = {
    "type": "object",
    "properties": {
        "children_step_ids": {"type": "array", "items": {"type": "string", "pattern": UUID_pattern}},
        "additionalProperties": False
    }
}

patch_schema_routes = {
    "type": "object",
    "properties": {
        "discover_new_neighbours": {"type": "boolean"},
        "check_current_neighbours": {"type": "boolean"},
        "server_id": {"type": "string",
                      "pattern": UUID_pattern},
        "server_list": {"type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "pattern": UUID_pattern},
                                "gateway": {"anyOf": [
                                    {"type": "string",
                                     "pattern": UUID_pattern},
                                    {"type": "null"}
                                ]},
                                "cost": {"anyOf": [
                                    {"type": "integer",
                                     "minimum": 0},
                                    {"type": "null"}
                                ]}
                            },
                            "required": ["id", "gateway", "cost"]
                        }
                        }
    },
    "additionalProperties": False
}

orchestration_post = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "integer", "minimum": 1},
        "description": {"type": "string"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"}
    },
    "required": ["name", "version"],
    "additionalProperties": False
}

orchestration_patch = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "integer", "minimum": 1},
        "description": {"type": "string"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"}
    },
    "additionalProperties": False
}

post_schema_routes = {
    "type": "object",
    "properties": {
        "discover_new_neighbours": {"type": "boolean"},
        "check_current_neighbours": {"type": "boolean"}
    },
    "additionalProperties": False
}

transfers_post = {
    "type": "object",
    "properties": {
        "software_id": {"type": "string",
                        "pattern": UUID_pattern},
        "dest_path": {"type": "string"},
        "filename": {"type": "string"},
        "num_chunks": {"type": "integer",
                       "minimum": 0},
        "force": {"type": "boolean"},
        "size": {"type": "integer"},
        "checksum": {"type": "string"},
    },
    "additionalProperties": False
}

transfer_post = {
    "type": "object",
    "properties": {
        "transfer_id": {"type": "string",
                        "pattern": UUID_pattern},
        "chunk": {"type": "integer",
                  "minimum": 0},
        "content": {"type": "string"},
    },
    "required": ["transfer_id", "chunk", "content"],
    "additionalProperties": False
}

schema_post_log = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "data": {"type": "string"},
    },
    "required": ["data"],
    "additionalProperties": False
}

schema_create_log = {
    "type": "object",
    "properties": {
        "src_server_id": {"type": "string",
                          "pattern": UUID_pattern},
        "target": {"type": "string"},
        "include": {"type": "string"},
        "exclude": {"type": "string"},
        "dst_server_id": {"type": "string",
                          "pattern": UUID_pattern},
        "dest_folder": {"type": "string"},
        "recursive": {"type": "boolean"},
    },
    "required": ["src_server_id", "target", "dst_server_id"],
    "additionalProperties": False
}

schema_patch_log = {
    "type": "object",
    "properties": {
        "include": {"type": "string",
                    "format": "regex"},
        "exclude": {"type": "string",
                    "format": "regex"},
        "dest_folder": {"type": "string"},
        "recursive": {"type": "boolean"},
    },
    "additionalProperties": False
}

schema_create_user = {
    "type": "object",
    "properties": {
        "user": {"type": "string"},
        "password": {"type": "string"},
        "email": {"type": "string",
                  "format": "email"}
    },
    "required": ["user", "password", "email"],
    "additionalProperties": False
}

schema_patch_user = {
    "type": "object",
    "properties": {
        "email": {"type": "string",
                  "format": "email"},
        "active": {"type": "boolean"}
    },
    "additionalProperties": False
}
