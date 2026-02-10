from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import json
import base64


from database import SessionLocal, PushSubscription
from push_config import get_vapid_keys, send_push_notification
from dependencies import get_current_user

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class SubscriptionSchema(BaseModel):
    endpoint: str
    keys: dict

class NotificationSchema(BaseModel):
    title: str
    body: str
    url: Optional[str] = "/"

@router.get("/vapid-key")
def get_vapid_public_key():
    keys = get_vapid_keys()
    if not keys:
        raise HTTPException(status_code=500, detail="VAPID keys not configured")
    
    # The browser expects the public key as a Uint8Array. 
    # Usually this is the raw 65-byte uncompressed point, Base64URL encoded.
    # Our push_config saved the PEM format. We will extract the base64 part.
    public_key_pem = keys["publicKey"]
    # Strip headers and newlines
    public_key_base64 = public_key_pem.replace("-----BEGIN PUBLIC KEY-----", "") \
                                     .replace("-----END PUBLIC KEY-----", "") \
                                     .replace("\n", "").strip()
    
    return {"publicKey": public_key_base64}

@router.post("/subscribe")
def subscribe(subscription: SubscriptionSchema, db: Session = Depends(get_db)):
    # Check if already exists
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == subscription.endpoint).first()
    if existing:
        return {"message": "Already subscribed"}

    new_sub = PushSubscription(
        endpoint=subscription.endpoint,
        p256dh=subscription.keys.get("p256dh"),
        auth=subscription.keys.get("auth")
    )
    db.add(new_sub)
    db.commit()
    return {"message": "Subscribed successfully"}

@router.post("/unsubscribe")
def unsubscribe(subscription: SubscriptionSchema, db: Session = Depends(get_db)):
    db.query(PushSubscription).filter(PushSubscription.endpoint == subscription.endpoint).delete()
    db.commit()
    return {"message": "Unsubscribed successfully"}

@router.post("/send")
def send_notification(notification: NotificationSchema, db: Session = Depends(get_db)):
    """Admin endpoint to send notification to ALL subscribers"""
    subs = db.query(PushSubscription).all()
    count = 0
    
    message = json.dumps({
        "title": notification.title,
        "body": notification.body,
        "url": notification.url,
        "icon": "/icon-192x192.png"
    })
    
    for sub in subs:
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        result = send_push_notification(sub_info, message)
        if result == "GONE":
            db.delete(sub) # Cleanup invalid subscription
        elif result:
            count += 1
            
    db.commit()
    return {"message": f"Sent to {count} subscribers"}


