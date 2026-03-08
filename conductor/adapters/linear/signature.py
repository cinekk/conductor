import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_linear_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify a Linear webhook HMAC-SHA256 signature.

    Linear signs the raw request body with the webhook secret and includes
    the hex digest in the `Linear-Signature` header.

    Uses hmac.compare_digest to prevent timing attacks.
    """
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
