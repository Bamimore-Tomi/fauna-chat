import unittest

from main import app


class TestCases(unittest.TestCase):
    def test_home(self):
        with app.test_client(self) as client:
            get_response = client.get("/")
            self.assertEqual(get_response.status_code, 302)

    def test_register(self):
        with app.test_client(self) as client:
            post_response = client.post("/register", data={"email": ""})
        post_detials = tester.post()
