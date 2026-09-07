import unittest

from server import ValidationError, normalize_payload


class NormalizePayloadTests(unittest.TestCase):
    def test_normalizes_valid_registration(self):
        result = normalize_payload(
            {
                "name": " Иван  Иванов ",
                "phone": "+7 (999) 123-45-67",
                "email": "USER@example.com",
                "consent": True,
                "lastname": "",
            }
        )
        self.assertEqual(result["name"], "Иван Иванов")
        self.assertEqual(result["email"], "user@example.com")
        self.assertEqual(result["source"], "Регистрация")

    def test_honeypot_does_not_create_registration(self):
        self.assertEqual(normalize_payload({"lastname": "bot"}), {"honeypot": "1"})

    def test_rejects_invalid_fields(self):
        invalid_payloads = (
            {"name": "A", "phone": "+79991234567", "email": "a@example.com", "consent": True},
            {"name": "Иван", "phone": "123", "email": "a@example.com", "consent": True},
            {"name": "Иван", "phone": "+79991234567", "email": "bad", "consent": True},
            {"name": "Иван", "phone": "+79991234567", "email": "a@example.com", "consent": False},
            {
                "name": "Иван",
                "phone": "+79991234567",
                "email": "a@example.com",
                "consent": True,
                "unexpected": "field",
            },
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                normalize_payload(payload)


if __name__ == "__main__":
    unittest.main()
