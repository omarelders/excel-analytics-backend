from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
import json
import base64

from database import PushSubscription
from push_config import get_vapid_keys, get_vapid_public_key_base64url, send_push_notification
from dependencies import get_current_user, require_admin, limiter

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

# Dependency
def get_db():
    from database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class SubscriptionKeys(BaseModel):
    p256dh: str = Field(..., min_length=1, max_length=512)
    auth: str = Field(..., min_length=1, max_length=512)

class SubscriptionSchema(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=2048)
    keys: SubscriptionKeys

class NotificationSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=1000)
    url: Optional[str] = Field("/", max_length=1000)


def _broadcast_push_worker(message: str):
    """Background task to broadcast push notifications without blocking HTTP worker"""
    from database import SessionLocal

    db = SessionLocal()
    try:
        subs = db.query(PushSubscription).all()
        for sub in subs:
            sub_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth
                }
            }
            try:
                result = send_push_notification(sub_info, message)
                if result == "GONE":
                    db.delete(sub)  # Cleanup invalid subscription
            except Exception:
                pass
        db.commit()
    finally:
        db.close()


@router.get("/vapid-key")
def get_vapid_public_key():
    keys = get_vapid_keys()
    if not keys:
        raise HTTPException(status_code=500, detail="VAPID keys not configured")
    
    try:
        public_key_base64 = get_vapid_public_key_base64url(keys["publicKey"])
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid VAPID public key configuration")
    
    return {"publicKey": public_key_base64}

@router.post("/subscribe")
def subscribe(subscription: SubscriptionSchema, db: Session = Depends(get_db)):
    try:
        existing = db.query(PushSubscription).filter(PushSubscription.endpoint == subscription.endpoint).first()
        if existing:
            return {"message": "Already subscribed"}

        new_sub = PushSubscription(
            endpoint=subscription.endpoint,
            p256dh=subscription.keys.p256dh,
            auth=subscription.keys.auth
        )
        db.add(new_sub)
        db.commit()
        return {"message": "Subscribed successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error subscribing to push notifications: {e}")
        raise HTTPException(status_code=500, detail="Failed to subscribe")

@router.post("/unsubscribe")
def unsubscribe(subscription: SubscriptionSchema, db: Session = Depends(get_db)):
    try:
        db.query(PushSubscription).filter(PushSubscription.endpoint == subscription.endpoint).delete()
        db.commit()
        return {"message": "Unsubscribed successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error unsubscribing from push notifications: {e}")
        raise HTTPException(status_code=500, detail="Failed to unsubscribe")

@router.post("/send")
@limiter.limit("1/minute")
def send_notification(
    request: Request,
    notification: NotificationSchema,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin endpoint to asynchronously broadcast notification to ALL subscribers"""
    subs_count = db.query(PushSubscription).count()
    
    message = json.dumps({
        "title": notification.title,
        "body": notification.body,
        "url": notification.url,
        "icon": "/icon-192x192.png"
    })
    
    background_tasks.add_task(_broadcast_push_worker, message)
    return {"message": f"Sent to {subs_count} subscribers"}
