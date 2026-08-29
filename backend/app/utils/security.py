import hmac
import hashlib

def verify_razorpay_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """
    Verifies the Razorpay webhook signature using HMAC-SHA256.
    
    :param raw_body: Exact raw request body bytes.
    :param signature: Header value of x-razorpay-signature.
    :param secret: Configured webhook secret.
    :return: True if valid signature, False otherwise.
    """
    if not signature or not secret:
        return False

    expected_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)
