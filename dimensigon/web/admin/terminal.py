"""
DShell Web Mode - Web-based terminal session management.

Provides a TerminalSession class for executing commands via the web interface
and a SessionManager for managing concurrent sessions per user.
"""
import uuid
from collections import defaultdict
from datetime import datetime

from dimensigon import __version__


class TerminalSession:
    """Manages a single web-based DShell terminal session."""

    def __init__(self, session_id, user_id):
        self.session_id = session_id
        self.user_id = user_id
        self.history = []
        self.output_buffer = []
        self.created_at = datetime.utcnow()

    def execute(self, command):
        """Execute a command and return output string."""
        command = command.strip()
        self.history.append(command)

        output = self._route_command(command)
        self.output_buffer.append(output)
        return output

    def _route_command(self, command):
        """Route a command to the appropriate handler."""
        parts = command.split()
        if not parts:
            return ""

        cmd = parts[0].lower()

        if cmd == "help":
            return (
                "Available commands:\n"
                "  help      - Show this help message\n"
                "  version   - Show DShell version\n"
                "  whoami    - Show current user\n"
                "  history   - Show command history\n"
                "  clear     - Clear terminal output"
            )
        elif cmd == "version":
            return f"DShell Web Mode v{__version__}"
        elif cmd == "whoami":
            return f"User: {self.user_id}"
        elif cmd == "history":
            if not self.history:
                return "(no history)"
            lines = []
            for i, entry in enumerate(self.history, 1):
                lines.append(f"  {i}  {entry}")
            return "\n".join(lines)
        elif cmd == "clear":
            self.output_buffer.clear()
            return ""
        else:
            return f"Command not recognized. Type 'help' for available commands."

    def get_history(self):
        """Return list of past commands."""
        return list(self.history)


class SessionManager:
    """Manages terminal sessions with per-user concurrency limits."""

    MAX_SESSIONS_PER_USER = 5

    def __init__(self):
        self._sessions = {}  # session_id -> TerminalSession
        self._user_sessions = defaultdict(set)  # user_id -> set of session_ids

    def create_session(self, user_id):
        """Create a new terminal session for a user. Returns session_id."""
        if len(self._user_sessions[user_id]) >= self.MAX_SESSIONS_PER_USER:
            raise ValueError(
                f"Maximum sessions ({self.MAX_SESSIONS_PER_USER}) reached for user"
            )

        session_id = str(uuid.uuid4())
        session = TerminalSession(session_id, user_id)
        self._sessions[session_id] = session
        self._user_sessions[user_id].add(session_id)
        return session_id

    def get_session(self, session_id):
        """Return a TerminalSession or None."""
        return self._sessions.get(session_id)

    def close_session(self, session_id):
        """Close and remove a terminal session."""
        session = self._sessions.pop(session_id, None)
        if session:
            self._user_sessions[session.user_id].discard(session_id)
            if not self._user_sessions[session.user_id]:
                del self._user_sessions[session.user_id]

    def active_sessions(self):
        """Return count of active sessions."""
        return len(self._sessions)


session_manager = SessionManager()
