from enum import Enum


class TypeMsg(Enum):
    INVOKE_CMD = 1
    COMPLETED_CMD = 2
    UNDO_CMD = 3
    PREVENT_LOCK = 4
    LOCK = 5
    UNLOCK = 6
    UPDATE_CATALOG = 7
    UPGRADE = 8
