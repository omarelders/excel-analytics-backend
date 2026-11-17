import os
import json
import base64
from pywebpush import webpush, WebPushException
from dotenv import load_dotenv

load_dotenv()

VAPID_FILE = "vapid_keys.json"


def get_vapid_public_key_base64url(public_key_str: str) -> str:
    """
    Convert a PEM PUBLIC KEY or base64/base64url public key string into the
    65-byte uncompressed P-256 point (0x04 || X || Y) encoded as URL-safe
    Base64 without padding, as required by PushManager.subscribe().
    """
    from cryptography.hazmat.primitives import serialization

    raw = (public_key_str or "").strip()
    if not raw:
        raise ValueError("Empty VAPID public key")

    if "-----BEGIN" in raw:
        pub = serialization.load_pem_public_key(raw.encode("utf-8"))
        uncompressed = pub.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        return base64.urlsafe_b64encode(uncompressed).decode("ascii").rstrip("=")

    cleaned = "".join(raw.split()).replace("+", "-").replace("/", "_")
    padded = cleaned + "=" * (-len(cleaned) % 4)
    decoded = base64.urlsafe_b64decode(padded)
    if len(decoded) == 65 and decoded[0] == 0x04:
        return base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")

    pub = serialization.load_der_public_key(decoded)
    uncompressed = pub.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(uncompressed).decode("ascii").rstrip("=")


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
