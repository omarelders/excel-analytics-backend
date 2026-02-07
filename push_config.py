import os
import json
from pywebpush import webpush, WebPushException
from dotenv import load_dotenv

load_dotenv()

VAPID_FILE = "vapid_keys.json"

def get_vapid_keys():
    """
    Get VAPID keys from environment variables or local file.
    If not found, generate new ones and save to file.
    """
    private_key = os.getenv("VAPID_PRIVATE_KEY")
    public_key = os.getenv("VAPID_PUBLIC_KEY")
    email = os.getenv("VAPID_EMAIL", "mailto:admin@goldroad.app")

    if private_key and public_key:
        return {"privateKey": private_key, "publicKey": public_key, "email": email}

    if os.path.exists(VAPID_FILE):
        try:
            with open(VAPID_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass

    # Generate new keys
    print("Generating new VAPID keys...")
    try:
        # Using pywebpush to generate isn't directly exposed as clean API in all versions
        # defaulting to using cryptography if available, or os.popen for CLI
        # But simpler: Instruct user or use a simple hack if pywebpush allows
        # Actually, let's look at how to generate.
        # For now, we will fail if not present to prompt user, OR we implement generation.
        # To be safe and robust, I'll use a widely compatible method if possible, 
        # but importing cryptography just for this might be overkill if not installed.
        # pywebpush installs cryptography.
        
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        
        curve = ec.SECP256R1()
        private_key_obj = ec.generate_private_key(curve)
        public_key_obj = private_key_obj.public_key()
        
        private_pem = private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        # We need the raw numbers or base64url encoded for VAPID? 
        # pywebpush takes PEM path or string.
        # However, for the frontend we need the Public Key in Base64URL format (or raw bytes).
        
        # Actually pywebpush handles PEM. But frontend needs public key.
        # Converting PEM to the required format for frontend is tricky without libs.
        # Let's try to stick to what py web push expects.
        
        # Better approach: Just save the keys and let the router serve the public one.
        
        keys = {
            "privateKey": private_pem.decode('utf-8'),
            "publicKey": public_key_obj.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8'),
            "email": email
        }
        
        with open(VAPID_FILE, "w") as f:
            json.dump(keys, f, indent=2)
            
        return keys
        
    except ImportError:
        print("Cryptography module not found. Cannot generate keys.")
        return None

def send_push_notification(subscription_info, message_body):
    """
    Send a push notification to a single subscription
    subscription_info: dict with endpoint, keys: { p256dh, auth }
    """
    keys = get_vapid_keys()
    if not keys:
        print("VAPID keys not configured.")
        return False

    try:
        webpush(
            subscription_info=subscription_info,
            data=message_body,
            vapid_private_key=keys["privateKey"],
            vapid_claims={"sub": keys["email"]}
        )
        return True
    except WebPushException as ex:
        print(f"Web Push Failed: {ex}")
        if ex.response and ex.response.status_code == 410:
            return "GONE" # Subscription expired
        return False
    except Exception as e:
        print(f"Error sending push: {e}")
        return False
