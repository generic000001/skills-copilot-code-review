"""
Announcement endpoints for the High School Management System API
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import announcements_collection, sessions_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementPayload(BaseModel):
    message: str
    expiration_date: str
    start_date: Optional[str] = None


def _parse_date(value: Optional[str], field_name: str, required: bool = False) -> Optional[date]:
    if value is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must use YYYY-MM-DD format"
        )


def _validate_signed_in_user(session_token: Optional[str]) -> None:
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = sessions_collection.find_one({"_id": session_token})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if datetime.now(timezone.utc) > session["expires_at"].replace(tzinfo=timezone.utc):
        sessions_collection.delete_one({"_id": session_token})
        raise HTTPException(status_code=401, detail="Session expired")


def _serialize_announcement(announcement: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(announcement["_id"]),
        "message": announcement["message"],
        "start_date": announcement.get("start_date"),
        "expiration_date": announcement["expiration_date"]
    }


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get currently active announcements for banner display."""
    today = date.today().isoformat()

    query: Dict[str, Any] = {
        "expiration_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": {"$exists": False}},
            {"start_date": {"$lte": today}}
        ]
    }

    announcements = [
        _serialize_announcement(announcement)
        for announcement in announcements_collection.find(query).sort("expiration_date", 1)
    ]

    return announcements


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_all_announcements(session_token: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Get all announcements for authenticated management."""
    _validate_signed_in_user(session_token)

    announcements = [
        _serialize_announcement(announcement)
        for announcement in announcements_collection.find().sort("expiration_date", 1)
    ]

    return announcements


@router.post("/manage", response_model=Dict[str, Any])
def create_announcement(payload: AnnouncementPayload, session_token: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Create a new announcement. Expiration date is required; start date is optional."""
    _validate_signed_in_user(session_token)

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    start_date = _parse_date(payload.start_date, "start_date", required=False)
    expiration_date = _parse_date(payload.expiration_date, "expiration_date", required=True)

    if start_date and expiration_date and start_date > expiration_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before expiration_date")

    document = {
        "message": message,
        "start_date": start_date.isoformat() if start_date else None,
        "expiration_date": expiration_date.isoformat()
    }

    result = announcements_collection.insert_one(document)
    inserted = {**document, "_id": result.inserted_id}

    return _serialize_announcement(inserted)


@router.put("/manage/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    session_token: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an existing announcement by id."""
    _validate_signed_in_user(session_token)

    if not ObjectId.is_valid(announcement_id):
        raise HTTPException(status_code=400, detail="Invalid announcement id")

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    start_date = _parse_date(payload.start_date, "start_date", required=False)
    expiration_date = _parse_date(payload.expiration_date, "expiration_date", required=True)

    if start_date and expiration_date and start_date > expiration_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before expiration_date")

    result = announcements_collection.update_one(
        {"_id": ObjectId(announcement_id)},
        {
            "$set": {
                "message": message,
                "start_date": start_date.isoformat() if start_date else None,
                "expiration_date": expiration_date.isoformat()
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated = announcements_collection.find_one({"_id": ObjectId(announcement_id)})
    return _serialize_announcement(updated)


@router.delete("/manage/{announcement_id}", response_model=Dict[str, str])
def delete_announcement(announcement_id: str, session_token: Optional[str] = Query(None)) -> Dict[str, str]:
    """Delete an announcement by id."""
    _validate_signed_in_user(session_token)

    if not ObjectId.is_valid(announcement_id):
        raise HTTPException(status_code=400, detail="Invalid announcement id")

    result = announcements_collection.delete_one({"_id": ObjectId(announcement_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}
