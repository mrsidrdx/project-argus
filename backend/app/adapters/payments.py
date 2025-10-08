import uuid
from typing import Any, Dict


# In-memory store for demo purposes
_payments_store: Dict[str, Dict[str, Any]] = {}
_refunds_store: Dict[str, Dict[str, Any]] = {}


def create_payment(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a payment.
    
    Expected params:
    - amount: number
    - currency: string  
    - vendor_id: string
    - memo: string (optional)
    """
    required_fields = ["amount", "currency", "vendor_id"]
    for field in required_fields:
        if field not in params:
            raise ValueError(f"Missing required field: {field}")
    
    payment_id = str(uuid.uuid4())
    payment = {
        "payment_id": payment_id,
        "amount": params["amount"],
        "currency": params["currency"],
        "vendor_id": params["vendor_id"],
        "status": "created"
    }
    
    if "memo" in params:
        payment["memo"] = params["memo"]
    
    _payments_store[payment_id] = payment
    return payment


def refund_payment(params: Dict[str, Any]) -> Dict[str, Any]:
    """Refund a payment.
    
    Expected params:
    - payment_id: string
    - reason: string (optional)
    """
    if "payment_id" not in params:
        raise ValueError("Missing required field: payment_id")
    
    payment_id = params["payment_id"]
    if payment_id not in _payments_store:
        raise ValueError(f"Payment {payment_id} not found")
    
    refund_id = str(uuid.uuid4())
    refund = {
        "refund_id": refund_id,
        "payment_id": payment_id,
        "status": "refunded"
    }
    
    if "reason" in params:
        refund["reason"] = params["reason"]
    
    _refunds_store[refund_id] = refund
    return refund
