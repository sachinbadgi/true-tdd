from typing import Annotated
from typing import Callable
from typing import ClassVar

MutantDict = Annotated[dict[str, Callable], "Mutant"] # type: ignore


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None): # type: ignore
    """Forward call to original or mutated function, depending on the environment"""
    import os # type: ignore
    mutant_under_test = os.environ['MUTANT_UNDER_TEST'] # type: ignore
    if mutant_under_test == 'fail': # type: ignore
        from mutmut.__main__ import MutmutProgrammaticFailException # type: ignore
        raise MutmutProgrammaticFailException('Failed programmatically')       # type: ignore
    elif mutant_under_test == 'stats': # type: ignore
        from mutmut.__main__ import record_trampoline_hit # type: ignore
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__) # type: ignore
        # (for class methods, orig is bound and thus does not need the explicit self argument)
        result = orig(*call_args, **call_kwargs) # type: ignore
        return result # type: ignore
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_' # type: ignore
    if not mutant_under_test.startswith(prefix): # type: ignore
        result = orig(*call_args, **call_kwargs) # type: ignore
        return result # type: ignore
    mutant_name = mutant_under_test.rpartition('.')[-1] # type: ignore
    if self_arg is not None: # type: ignore
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs) # type: ignore
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs) # type: ignore
    return result # type: ignore
def add(a: int, b: int) -> int:
    args = [a, b]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_add__mutmut_orig, x_add__mutmut_mutants, args, kwargs, None)
def x_add__mutmut_orig(a: int, b: int) -> int:
    return a + b
def x_add__mutmut_1(a: int, b: int) -> int:
    return a - b

x_add__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_add__mutmut_1': x_add__mutmut_1
}
x_add__mutmut_orig.__name__ = 'x_add'

def divide(a: float, b: float) -> float:
    args = [a, b]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_divide__mutmut_orig, x_divide__mutmut_mutants, args, kwargs, None)

def x_divide__mutmut_orig(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def x_divide__mutmut_1(a: float, b: float) -> float:
    if b != 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def x_divide__mutmut_2(a: float, b: float) -> float:
    if b == 1:
        raise ValueError("Cannot divide by zero")
    return a / b

def x_divide__mutmut_3(a: float, b: float) -> float:
    if b == 0:
        raise ValueError(None)
    return a / b

def x_divide__mutmut_4(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("XXCannot divide by zeroXX")
    return a / b

def x_divide__mutmut_5(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("cannot divide by zero")
    return a / b

def x_divide__mutmut_6(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("CANNOT DIVIDE BY ZERO")
    return a / b

def x_divide__mutmut_7(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a * b

x_divide__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_divide__mutmut_1': x_divide__mutmut_1, 
    'x_divide__mutmut_2': x_divide__mutmut_2, 
    'x_divide__mutmut_3': x_divide__mutmut_3, 
    'x_divide__mutmut_4': x_divide__mutmut_4, 
    'x_divide__mutmut_5': x_divide__mutmut_5, 
    'x_divide__mutmut_6': x_divide__mutmut_6, 
    'x_divide__mutmut_7': x_divide__mutmut_7
}
x_divide__mutmut_orig.__name__ = 'x_divide'

def multiply(a: int, b: int) -> int:
    args = [a, b]# type: ignore
    kwargs = {}# type: ignore
    return _mutmut_trampoline(x_multiply__mutmut_orig, x_multiply__mutmut_mutants, args, kwargs, None)

def x_multiply__mutmut_orig(a: int, b: int) -> int:
    return a * b

def x_multiply__mutmut_1(a: int, b: int) -> int:
    return a / b

x_multiply__mutmut_mutants : ClassVar[MutantDict] = { # type: ignore
'x_multiply__mutmut_1': x_multiply__mutmut_1
}
x_multiply__mutmut_orig.__name__ = 'x_multiply'
