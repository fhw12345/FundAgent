"""
In-memory session management with TTL-based cleanup.
Following Factor 12: Stateless Service (state externalized to session store).

v0.2.0: In-memory implementation
v0.3.0+: Will be replaced with MongoDB/Redis persistence
"""

import asyncio
import uuid
from datetime import datetime, timedelta

import structlog

from .state import ChatSession

logger = structlog.get_logger()


class SessionManager:
    """
    In-memory session store with automatic TTL cleanup.

    Thread-safe for single-pod deployment.
    For multi-pod deployment, use Redis/MongoDB backend.
    """

    def __init__(self, ttl_minutes: int = 30, cleanup_interval_seconds: int = 60):
        """
        Initialize session manager.

        Args:
            ttl_minutes: Session expiration time in minutes
            cleanup_interval_seconds: How often to run cleanup task
        """
        self._sessions: dict[str, ChatSession] = {}
        self._access_times: dict[str, datetime] = {}
        self._ttl_minutes = ttl_minutes
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_task: asyncio.Task | None = None

        logger.info(
            "SessionManager initialized",
            ttl_minutes=ttl_minutes,
            cleanup_interval=cleanup_interval_seconds,
        )

    async def start(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("SessionManager cleanup task started")

    async def stop(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("SessionManager cleanup task stopped")

    def create_session(self, user_id: str | None = None) -> ChatSession:
        """
        Create a new chat session.

        Args:
            user_id: Optional user identifier

        Returns:
            New ChatSession with unique session_id
        """
        session_id = str(uuid.uuid4())
        session = ChatSession(session_id=session_id, user_id=user_id)

        self._sessions[session_id] = session
        self._access_times[session_id] = datetime.utcnow()

        logger.info("Session created", session_id=session_id, user_id=user_id)
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """
        Retrieve session by ID, updating access time.

        Args:
            session_id: Session identifier

        Returns:
            ChatSession if found and not expired, None otherwise
        """
        if session_id not in self._sessions:
            logger.debug("Session not found", session_id=session_id)
            return None

        # Check if expired
        if self._is_expired(session_id):
            logger.info("Session expired", session_id=session_id)
            self._delete_session(session_id)
            return None

        # Update access time
        self._access_times[session_id] = datetime.utcnow()
        return self._sessions[session_id]

    def update_session(self, session: ChatSession) -> None:
        """
        Update an existing session.

        Args:
            session: Updated ChatSession object
        """
        if session.session_id in self._sessions:
            self._sessions[session.session_id] = session
            self._access_times[session.session_id] = datetime.utcnow()
            logger.debug("Session updated", session_id=session.session_id)
        else:
            logger.warning(
                "Cannot update non-existent session", session_id=session.session_id
            )

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        return self._delete_session(session_id)

    def get_session_count(self) -> int:
        """Get current number of active sessions."""
        return len(self._sessions)

    def _is_expired(self, session_id: str) -> bool:
        """Check if a session has expired."""
        if session_id not in self._access_times:
            return True

        last_access = self._access_times[session_id]
        expiry_time = last_access + timedelta(minutes=self._ttl_minutes)
        return datetime.utcnow() > expiry_time

    def _delete_session(self, session_id: str) -> bool:
        """Internal method to delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            del self._access_times[session_id]
            logger.debug("Session deleted", session_id=session_id)
            return True
        return False

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error("Error in cleanup loop", error=str(e))

    async def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions from memory."""
        expired_sessions = [
            session_id
            for session_id in list(self._sessions.keys())
            if self._is_expired(session_id)
        ]

        for session_id in expired_sessions:
            self._delete_session(session_id)

        if expired_sessions:
            logger.info(
                "Cleanup completed",
                expired_count=len(expired_sessions),
                active_count=len(self._sessions),
            )


# Global singleton instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """
    Get global session manager instance.

    Returns:
        SessionManager singleton
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
