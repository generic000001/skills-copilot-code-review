"""
Authentication endpoints for the High School Management System API
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..database import teachers_collection, sessions_collection, verify_password

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

SESSION_TTL_HOURS = 24


@router.post("/login")
def login(username: str, password: str) -> Dict[str, Any]:
    """Login a teacher account and return a session token"""
    # Find the teacher in the database
    teacher = teachers_collection.find_one({"_id": username})

    # Verify password using Argon2 verifier from database.py
    if not teacher or not verify_password(teacher.get("password", ""), password):
        raise HTTPException(
            status_code=401, detail="Invalid username or password")

    # Generate a secure random session token and persist it
    token = secrets.token_hex(32)
    now = datetime.now(timezone.utc)
    sessions_collection.insert_one({
        "_id": token,
        "teacher_username": username,
        "created_at": now,
        "expires_at": now + timedelta(hours=SESSION_TTL_HOURS),
    })

    # Return teacher information (excluding password) along with the session token
    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"],
        "token": token,
    }


@router.get("/check-session")
def check_session(session_token: str) -> Dict[str, Any]:
    """Check if a session token is valid"""
    session = sessions_collection.find_one({"_id": session_token})

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if datetime.now(timezone.utc) > session["expires_at"].replace(tzinfo=timezone.utc):
        sessions_collection.delete_one({"_id": session_token})
        raise HTTPException(status_code=401, detail="Session expired")

    teacher = teachers_collection.find_one({"_id": session["teacher_username"]})
    if not teacher:
        raise HTTPException(status_code=401, detail="Teacher not found")

    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"],
        "token": session_token,
    }


@router.post("/logout")
def logout(session_token: str) -> Dict[str, str]:
    """Invalidate a session token"""
    sessions_collection.delete_one({"_id": session_token})
    return {"message": "Logged out successfully"}
