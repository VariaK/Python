import time
from minitest import fixture

@fixture(scope="session")
def db_connection():
    time.sleep(0.01)
    yield "FakeDBConn"

@fixture(scope="function")
def mock_api():
    return {"status": 200, "user": "test_user"}
