from dimensigon.domain.entities import Scope, ActionType, LogMode
from dimensigon.domain.entities.transfer import Status

UUID_pattern = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

login_post = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "password": {"type": "string"}

    },
    "required": ["username", "password"],
    "additionalProperties": False
}

healthcheck_post = {
    "type": "object",
    "properties": {
        "exclude": {"type": "array",
                    "items": {"type": "string", "pattern": UUID_pattern}},
        "heartbeat": {"type": "string"},
    },
    "required": ["exclude", "heartbeat"],
    "additionalProperties": False
}

cluster_post = {
    "type": "array",
    "items": {"type": "object",
              "properties": {
                  "id": {"type": "string", "pattern": UUID_pattern},
                  "birth": {"type": "string"},
                  "keepalive": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                  "death": {"anyOf": [{"type": "string"}, {"type": "null"}]}
              },
              "required": ["id", "birth"]
              }

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
        "force": {"type": "boolean"},
    },
    "required": ["scope", "applicant"],
    "additionalProperties": False
}

manager_server_ignore_lock_post = {
    "type": "object",
    "properties": {
        "server_ids": {"type": "array",
                       "items": {"type": "string", "pattern": UUID_pattern},
                       },
        "ignore_on_lock": {"type": "boolean"}
    },
    "required": ["ignore_on_lock", "server_ids"],
    "additionalProperties": False
}

send_post = {
    "type": "object",
    "properties": {
        "software_id": {"type": "string",
                        "pattern": UUID_pattern},
        "software": {"type": "string"},
        "version": {"type": "string"},
        "file": {"type": "string"},
        "dest_server_id": {"type": "string",
                           "pattern": UUID_pattern},
        "dest_path": {"type": "string"},
        "chunk_size": {"type": "integer",  # size in MB
                       "minimum": 1,
                       "maximum": 1 * 1024,
                       # "multipleOf": 1024
                       },
        "max_senders": {"type": "integer",
                        "minimum": 1},
        "background": {"type": "boolean"},
        "force": {"type": "boolean"},
        "include_transfer_data": {"type": "boolean"},
    },
    "oneOf": [{"required": ["software_id", "dest_server_id"]},
              {"required": ["software", "version", "dest_server_id"]},
              {"required": ["file", "dest_server_id"]}],
    "additionalProperties": False
}

software_post = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "family": {"type": "string"},
        "file": {"type": "string"}
    },
    "required": ["name", "version", "file"],
    "additionalProperties": False
}

software_patch = {
    "type": "object",
    "properties": {
        "server_id": {"type": "string",
                      "pattern": UUID_pattern},
        "path": {"type": "string"},
    },
    "required": ["server_id", "path"],
    "additionalProperties": False
}

software_servers_put = {
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

action_type_pattern = f"^({'|'.join([at.name for at in ActionType if at.name != 'NATIVE'])})$"
action_template_post = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},
        "code": {"type": "string"},
        "parameters": {"type": "object"},
        "expected_stdout": {"type": "string"},
        "expected_stderr": {"type": "string"},
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": {"type": "string"},
        "post_process": {"type": "string"},
    },
    "if": {
        "properties": {"action_type": {"const": "SEND"}}
    },
    "then": {
        "required": ["name", "action_type"],
    },
    "else": {
        "properties": {"code": {"type": "string"}},
        "required": ["name", "action_type", "code"],
    },
    "required": ["name", "action_type", "code"],
    "additionalProperties": False
}

action_template_patch = {
    "type": "object",
    "properties": {
        "action_type": {"type": "string",
                        "pattern": f"^({'|'.join([at.name for at in ActionType])})$"},
        "code": {"type": "string"},
        "parameters": {"type": "object"},
        "expected_stdout": {"type": "string"},
        "expected_stderr": {"type": "string"},
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": {"type": "string"},
        "post_process": {"type": "string"},
    },
    "additionalProperties": False
}

_step_post = {
    "type": "object",
    "properties": {
        "id": {"anyOf": [{"type": "string"},
                         {"type": "integer", "minimum": 1}]},
        "orchestration_id": {"type": "string",
                             "pattern": UUID_pattern},
        "undo": {"type": "boolean"},
        "name": {"type": "string"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "action_template_id": {"type": "string",
                               "pattern": UUID_pattern},
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},
        "undo_on_error": {"type": "boolean"},
        "code": {"type": "string"},
        "parameters": {"type": "object"},
        "expected_stdout": {"type": "string"},
        "expected_stderr": {"type": "string"},
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": {"type": "string"},
        "post_process": {"type": "string"},
        "parent_step_ids": {"type": "array",
                            "items": {"anyOf": [{"type": "string", "pattern": UUID_pattern},
                                                {"type": "integer", "minimum": 1}]
                                      }
                            },
        "target": {"anyOf": [{"type": "string"},
                             {"type": "array", "items": {"type": "string"}}]}
    },
    "oneOf": [{"required": ["orchestration_id", "undo", "action_template_id"]},
              {"required": ["orchestration_id", "undo", "action_type"]}],
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
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},

        "code": {"type": "string"},
        "parameters": {"type": "object"},
        "expected_stdout": {"type": "string"},
        "expected_stderr": {"type": "string"},
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": {"type": "string"},
        "post_process": {"type": "string"},
        "name": {"type": "string"},
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
    "oneOf": [{"required": ["undo", "action_template_id"]},
              {"required": ["undo", "action_type"]}],
    "additionalProperties": False
}

step_patch = {
    "type": "object",
    "properties": {
        "undo": {"type": "boolean"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "action_template_id": {"type": "string",
                               "pattern": UUID_pattern},
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},
        "undo_on_error": {"type": "boolean"},
        "code": {"type": "string"},
        "parameters": {"type": "object"},
        "expected_stdout": {"type": "string"},
        "expected_stderr": {"type": "string"},
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": {"type": "string"},
        "post_process": {"type": "string"},
        "name": {"type": "string"},
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

routes_patch = {
    "type": "object",
    "properties": {
        "server_id": {"type": "string",
                      "pattern": UUID_pattern},
        "route_list": {"type": "array",
                       "items": {
                           "type": "object",
                           "properties": {
                               "destination_id": {"type": "string", "pattern": UUID_pattern},
                               "proxy_server_id": {"anyOf": [
                                   {"type": "string",
                                    "pattern": UUID_pattern},
                                   {"type": "null"}
                               ]},
                               "gate_id": {"anyOf": [
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
                           "required": ["destination_id", "gate_id", "cost"]
                       }
                       },
        "exclude": {"type": "array",
                    "items": {"type": "string",
                              "pattern": UUID_pattern}}
    },
    "additionalProperties": False,
    "required": ["server_id", "route_list"]
}

routes_post = {
    "type": "object",
    "properties": {
        "discover_new_neighbours": {"type": "boolean"},
        "check_current_neighbours": {"type": "boolean"},
        "retries": {"type": "integer", "minimum": 1},
        "timeout": {"type": "number", "minimum": 0},
        "background": {"type": "boolean"}
    },
    "additionalProperties": False
}

orchestration_post = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"}
    },
    "required": ["name"],
    "additionalProperties": False
}

orchestration_step = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "undo": {"type": "boolean"},
        "name": {"type": "string"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "action_template_id": {"type": "string",
                               "pattern": UUID_pattern},
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},
        "undo_on_error": {"type": "boolean"},
        "code": {"type": "string"},
        "parameters": {"type": "object"},
        "expected_stdout": {"type": "string"},
        "expected_stderr": {"type": "string"},
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": {"type": "string"},
        "post_process": {"type": "string"},
        "parent_step_ids": {"type": "array",
                            "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]}
                            },
        "target": {"anyOf": [{"type": "string"},
                             {"type": "array", "items": {"type": "string"}}]}
    },
    "oneOf": [{"required": ["undo", "action_template_id"]},
              {"required": ["undo", "action_type"]}],
    "additionalProperties": False
}


orchestration_full = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"},
        "steps": {"type": "array",
                  "items": orchestration_step}
    },
    "required": ["name", "steps"],
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


launch_orchestration_post = {
    "type": "object",
    "properties": {
        'hosts': {"anyOf": [{"type": "string"},
                            {"type": "array",
                             "items": {"type": "string"},
                             "minItems": 1},
                            {"type": "object",
                             "patternProperties": {
                                 ".*": {"anyOf": [{"type": "string"},
                                                  {"type": "array",
                                                   "items": {"type": "string"},
                                                   "minItems": 1
                                                   },
                                                  ]
                                        },
                             },
                             }]
                  },
        "params": {"type": "object"},
        "background": {"type": "boolean"}
    },
    "required": ["hosts"],
    "additionalProperties": False,
}



transfers_post = {
    "type": "object",
    "properties": {
        "software_id": {"type": "string",
                        "pattern": UUID_pattern},
        "filename": {"type": "string"},         # specify filename if you want to send a file instead of a software
        "size": {"type": "integer"},
        "checksum": {"type": "string"},
        "dest_path": {"type": "string"},        # if not specified DM_SOFTWARE_REPO is used
        "num_chunks": {"type": "integer",
                       "minimum": 0},
        "cancel_pending": {"type": "boolean"},  # cancels pending transfers from the same file in the same folder
        "force": {"type": "boolean"},           # forces to transfer file even if it exists in the destination

    },
    "required": ['num_chunks'],
    "additionalProperties": False
}

transfer_post = {
    "type": "object",
    "properties": {
        "chunk": {"type": "integer",
                  "minimum": 0},
        "content": {"type": "string"},
    },
    "required": ["chunk", "content"],
    "additionalProperties": False
}

transfer_patch = {
    "type": "object",
    "properties": {
        "status": {"type": "string",
                   "pattern": f"^({'|'.join([s.name for s in Status])})$"},
    },
    "required": ["status"],
    "additionalProperties": False
}

logs_post = {
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
        "mode": {"type": "string",
                 "pattern": f"^({'|'.join([m.name for m in LogMode])})$"}
    },
    "additionalProperties": False,
    "required": ["src_server_id", "target", "dst_server_id"],
}

log_patch = {
    "type": "object",
    "properties": {
        "include": {"type": "string",
                    "format": "regex"},
        "exclude": {"type": "string",
                    "format": "regex"},
        "dest_folder": {"type": "string"},
        "recursive": {"type": "boolean"},
        "mode": {"type": "string",
                 "pattern": f"^({'|'.join([m.name for m in LogMode])})$"}
    },
    "additionalProperties": False
}

log_post = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "data": {"type": "string"},
        "compress": {"type": "boolean"}
    },
    "required": ["data"],
    "additionalProperties": False
}

users_post = {
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

user_patch = {
    "type": "object",
    "properties": {
        "email": {"type": "string",
                  "format": "email"},
        "active": {"type": "boolean"}
    },
    "additionalProperties": False
}

launch_command_post = {
    "type": "object",
    "properties": {
        "command": {"type": "string"},
        "target": {"anyOf": [{"type": "string"},
                            {"type": "array",
                             "items": {"type": "string"}},
                            ]
                  },
        "timeout": {"type": "integer",
                    "minimum": 1},
        "input": {"type": "string"},
    },
    "required": ["command"],
    "additionalProperties": False,
}

servers_delete = {
    "type": "object",
    "properties": {"server_ids": {"type": "array",
                                  "items": {"type": "string",
                                            "pattern": UUID_pattern}}
                   },
    "additionalProperties": False,
    "required": ["server_ids"]
}

server_post = {
    "type": "object",
    "properties": {
        # "gates": {"type": "object",
        #           "properties": {
        #               "dns_or_ip": {"type": "string"},
        #               "port": {"type": "integer",
        #                        "minimum": 1,
        #                        "maximum": 65535},
        #               "hidden": {"type": "boolean"},
        #               "required": ["dns_or_ip", "port"],
        #               "additionalProperties": False,
        #           }},
        "granules": {"type": "array",
                     "items": {"type": "string"}}
    },
    "additionalProperties": False,
    "required": ["granules"]
}

server_patch = {
    "type": "object",
    "properties": {
        "gates": {"type": "array",
                  "items": {"type": "object",
                            "properties": {
                                "dns_or_ip": {"type": "string"},
                                "port": {"type": "integer",
                                         "minimum": 1,
                                         "maximum": 65535},
                                "hidden": {"type": "boolean"},

                            },
                            "required": ["dns_or_ip", "port"],
                            "additionalProperties": False,
                            }
                  },
        "granules": {"type": "array",
                     "items": {"type": "string"}},
        "ignore_on_lock": {"type": "boolean"},
    },
    "additionalProperties": False,
}

files_post = {
    "properties": {
        "src_server_id": {"type": "string",
                          "pattern": UUID_pattern},
        "target": {"type": "string"},
        "dest_folder": {"type": "string"},
        "destinations": {"type": "array",
                         "items": {"type": "object",
                                   "properties": {
                                       "dst_server_id": {"type": "string",
                                                         "pattern": UUID_pattern},
                                       "dest_folder": {"type": "string"}

                                   },
                                   "required": ["dst_server_id"],
                                   "additionalProperties": False
                                   }
                         }
    },
    "required": ["src_server_id", "target"],
    "additionalProperties": False
}

file_patch = {
    "properties": {
        "src_server_id": {"type": "string",
                          "pattern": UUID_pattern},
        "target": {"type": "string"},
        "dest_folder": {"type": "string"},
        "destinations": {"type": "array",
                         "items": {"type": "object",
                                   "properties": {
                                       "dst_server_id": {"type": "string",
                                                         "pattern": UUID_pattern},
                                       "dest_folder": {"type": "string"}

                                   },
                                   "required": ["dst_server_id"],
                                   "additionalProperties": False
                                   }
                         }
    },
    "additionalProperties": False
}

file_post = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "data": {"type": "string"},
        "force": {"type": "boolean"}

    },
    "required": ["data", "file"],
    "additionalProperties": False
}