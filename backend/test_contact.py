import json
import os
import unittest
from unittest.mock import MagicMock, patch

import contact


VALID = {
    "name": "Alex Rivera",
    "email": "Alex@example.com",
    "subject": "integration",
    "message": "We need historical invoice details after moving online.",
    "website": "",
    "company": "Test Company",
    "attribution": {"utm_source": "linkedin"},
}


class ContactTests(unittest.TestCase):
    def test_rejects_short_message_before_storage(self):
        data = {**VALID, "message": "too short"}
        with patch.object(contact.boto3, "resource") as resource:
            result = contact.handler({"body": json.dumps(data)}, None)
        self.assertEqual(result["statusCode"], 400)
        resource.assert_not_called()

    def test_stores_and_notifies(self):
        with patch.dict(os.environ, {
            "CONTACT_TABLE": "contacts",
            "SES_FROM_EMAIL": "sender@example.com",
            "SES_ADMIN_EMAIL": "admin@example.com",
        }), patch.object(contact.boto3, "resource") as resource, patch.object(contact.boto3, "client") as client:
            result = contact.handler({"body": json.dumps(VALID)}, None)
        self.assertEqual(result["statusCode"], 202)
        item = resource.return_value.Table.return_value.put_item.call_args.kwargs["Item"]
        self.assertEqual(item["source"], "salesforcepartnersandiego")
        self.assertEqual(item["email"], "alex@example.com")
        self.assertEqual(item["id"], json.loads(result["body"])["contactId"])
        client.return_value.send_email.assert_called_once()

    def test_notification_failure_preserves_saved_inquiry(self):
        with patch.dict(os.environ, {
            "CONTACT_TABLE": "contacts", "SES_FROM_EMAIL": "sender@example.com",
            "SES_ADMIN_EMAIL": "admin@example.com",
        }), patch.object(contact.boto3, "resource") as resource, patch.object(contact.boto3, "client") as client:
            client.return_value.send_email.side_effect = RuntimeError("unavailable")
            result = contact.handler({"body": json.dumps(VALID)}, None)
        self.assertEqual(result["statusCode"], 202)
        resource.return_value.Table.return_value.put_item.assert_called_once()

    def test_rejects_invalid_inputs_before_storage(self):
        for changed in ({"website": "bot"}, {"subject": "other"}, {"email": "invalid"},
                        {"company": "x" * 201}, {"attribution": {"utm_source": []}}):
            with self.subTest(changed=changed), patch.object(contact.boto3, "resource") as resource:
                result = contact.handler({"body": json.dumps({**VALID, **changed})}, None)
                self.assertEqual(result["statusCode"], 400)
                resource.assert_not_called()

    def test_no_false_success_when_storage_fails(self):
        failing = MagicMock()
        failing.Table.return_value.put_item.side_effect = RuntimeError("unavailable")
        with patch.dict(os.environ, {"CONTACT_TABLE": "contacts"}), patch.object(contact.boto3, "resource", return_value=failing), patch.object(contact.boto3, "client") as client:
            result = contact.handler({"body": json.dumps(VALID)}, None)
        self.assertEqual(result["statusCode"], 503)
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
