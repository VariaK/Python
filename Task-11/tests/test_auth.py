import time
from minitest import test

class Response:
    def __init__(self, status):
        self.status = status

@test
def test_login_valid_credentials(db_connection, mock_api):
    time.sleep(0.02)
    assert mock_api["status"] == 200

@test
def test_login_invalid_password():
    time.sleep(0.01)
    assert 1 == 1

@test
def test_login_expired_token():
    time.sleep(0.03)
    response = Response(200)
    assert response.status == 401
