import unittest, random, string

from main import app


class TestCases(unittest.TestCase):
    def test_home(self):
        with app.test_client(self) as client:
            get_response = client.get("/")
            self.assertEqual(get_response.status_code, 302)

    def test_register(self):
        with app.test_client(self) as client:
            # Generate dummy username
            username = "".join([random.choice(string.ascii_letters) for i in range(7)])
            post_response_1 = client.post(
                "/register",
                data={
                    "email": username + "@gmail.com",
                    "username": f"test-{username}",
                    "password": f"password-{username}",
                },
            )
            # test is successful registration return a redirect to the login page
            self.assertEqual(post_response_1.status_code, 302)
        post_detials = tester.post()
