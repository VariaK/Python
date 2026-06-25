# minitest/__init__.py

def test(func):
    """Decorator to mark a function as a test."""
    func.__is_test__ = True
    return func

def fixture(scope="function"):
    """
    Decorator to mark a function as a fixture.
    Supported scopes: 'session', 'module', 'function'
    """
    def decorator(func):
        func.__is_fixture__ = True
        func.__fixture_scope__ = scope
        return func
    # Allow @fixture without parens
    if callable(scope):
        func = scope
        scope = "function"
        return decorator(func)
    return decorator

def parametrize(argnames, argvalues):
    """
    Decorator to parameterize a test.
    `argnames` can be a comma-separated string of argument names.
    `argvalues` should be an iterable of values or tuples of values.
    """
    def decorator(func):
        if not hasattr(func, "__parametrize__"):
            func.__parametrize__ = []
        func.__parametrize__.append((argnames, argvalues))
        return func
    return decorator

def skip(reason=""):
    """Decorator to unconditionally skip a test."""
    def decorator(func):
        func.__skip_reason__ = reason
        return func
    return decorator
