"""Salesforce website contact intake: validate, store, then notify by SES."""

import base64
import binascii
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import boto3


SUBJECTS = {
    "integration", "implementation", "ai-crm", "not-sure",
}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def validate_contact(data):
    if not isinstance(data, dict):
        raise ValueError("Invalid request")
    if data.get("website"):
        raise ValueError("Invalid request")

    values = {}
    for field in ("name", "email", "subject", "message"):
        value = data.get(field)
        if not isinstance(value, str):
            raise ValueError(f"{field} is required")
        values[field] = value.strip()

    if not 2 <= len(values["name"]) <= 100:
        raise ValueError("Name must be 2-100 characters")
    if len(values["email"]) > 254 or not EMAIL_PATTERN.fullmatch(values["email"]):
        raise ValueError("Enter a valid email address")
    if values["subject"] not in SUBJECTS:
        raise ValueError("Choose a valid subject")
    if not 10 <= len(values["message"]) <= 5000:
        raise ValueError("Message must be 10-5000 characters")
    company = data.get("company", "")
    if not isinstance(company, str) or len(company.strip()) > 200:
        raise ValueError("Company must be at most 200 characters")
    values["company"] = company.strip()
    attribution = data.get("attribution", {})
    if not isinstance(attribution, dict):
        raise ValueError("Invalid attribution")
    values["attribution"] = {}
    for key in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"):
        value = attribution.get(key, "")
        if not isinstance(value, str) or len(value) > 200:
            raise ValueError("Invalid attribution")
        if value:
            values["attribution"][key] = value
    values["email"] = values["email"].lower()
    return values


def handler(event, _context):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        except (binascii.Error, ValueError, UnicodeDecodeError):
            return response(400, {"error": "Invalid request"})
    if len(raw.encode("utf-8")) > 10_000:
        return response(413, {"error": "Message is too large"})

    try:
        values = validate_contact(json.loads(raw))
    except (ValueError, json.JSONDecodeError) as exc:
        return response(400, {"error": str(exc)})

    contact_id = str(uuid.uuid4())
    received_at = datetime.now(timezone.utc)
    item = {
        "id": contact_id,
        "receivedAt": received_at.isoformat(),
        "expiresAt": int((received_at + timedelta(days=180)).timestamp()),
        "source": "salesforcepartnersandiego",
        "status": "new",
        **values,
    }
    try:
        boto3.resource("dynamodb").Table(os.environ["CONTACT_TABLE"]).put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(id)",
        )
    except Exception:
        # Never report success if the message was not saved.
        print("Salesforce website contact storage failed")
        return response(503, {"error": "We could not receive your request. Please try email."})

    sender = os.environ["SES_FROM_EMAIL"]
    recipient = os.environ["SES_ADMIN_EMAIL"]
    subject = f"Salesforce website inquiry: {values['subject']}"
    body = (
        f"Reference: {contact_id}\n"
        f"Name: {values['name']}\n"
        f"Email: {values['email']}\n"
        f"Company: {values['company']}\n"
        f"Subject: {values['subject']}\n"
        f"Campaign: {json.dumps(values['attribution'])}\n\n"
        f"{values['message']}"
    )
    try:
        boto3.client("ses").send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient]},
            ReplyToAddresses=[values["email"]],
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
    except Exception:
        # The saved record remains available for follow-up.
        print(f"Salesforce website notification failed for {contact_id}")

    return response(202, {"contactId": contact_id, "message": "Request received"})
