import pytest
from calculator import add, divide, multiply, subtract

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

@pytest.mark.requirement("REQ-203")
def test_multiply_positive():
    assert multiply(3, 4) == 12

@pytest.mark.requirement("REQ-202")
def test_divide_normal():
    assert divide(10, 2) == 5.0

@pytest.mark.requirement("REQ-204")
def test_subtract_positive():
    assert subtract(5, 3) == 2

@pytest.mark.requirement("REQ-204")
def test_subtract_negative():
    assert subtract(3, 5) == -2
