import time
from minitest import test, parametrize, skip, fixture

@fixture(scope="function")
def temp_dir():
    yield "/tmp/test_dir_123"

@test
@parametrize("product_id, qty", [
    (1, 1),
    (2, 5),
    (99, 0)
])
def test_add_item(product_id, qty, temp_dir):
    time.sleep(0.01)
    assert qty >= 0
    assert product_id > 0

@test
@skip("no API key")
def test_checkout_stripe():
    assert False
