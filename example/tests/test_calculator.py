import pytest
from calculator import add, divide, multiply

@pytest.mark.requirement("REQ-201")
def test_add_positive():
    assert add(2, 3) == 5

@pytest.mark.requirement("REQ-201")
def test_add_negative():
    assert add(-1, 1) == 0

@pytest.mark.requirement("REQ-202")
def test_divide_by_zero_raises():
    with pytest.raises(ValueError):
        divide(10, 0)

# REQ-203 intentionally left untagged to demonstrate UNTESTED status
