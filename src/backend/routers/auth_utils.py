"""
Shared authentication utilities for the High School Management System API
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

from ..database import sessions_collection


def validate_session_token(session_token: Optional[str], auth_required_message: str = "Authentication required") -> None:
    """Verify that a session token exists in the database and has not expired.

    Raises HTTPException with status 401 if the token is missing, invalid, or expired.
    Expired sessions are removed from the database automatically.
    """
    if not session_token:
        raise HTTPException(status_code=401, detail=auth_required_message)

    session = sessions_collection.find_one({"_id": session_token})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # expires_at is stored as a naive UTC datetime by PyMongo; attach timezone before comparing
    if datetime.now(timezone.utc) > session["expires_at"].replace(tzinfo=timezone.utc):
        sessions_collection.delete_one({"_id": session_token})
        raise HTTPException(status_code=401, detail="Session expired")
