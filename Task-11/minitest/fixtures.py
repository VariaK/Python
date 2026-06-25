import inspect

FIXTURE_REGISTRY = {}

def register_fixture(name, func, scope):
    """Register a fixture function."""
    FIXTURE_REGISTRY[name] = {
        'func': func,
        'scope': scope
    }

class FixtureManager:
    """Manages fixture lifecycle (setup, cache, teardown)."""
    
    def __init__(self):
        self.session_cache = {}
        self.module_cache = {}
        self.teardowns = {'session': [], 'module': [], 'function': []}

    def get_fixture_kwargs(self, func, provided_params=None):
        """
        Resolve fixture dependencies for a function (test or another fixture).
        `provided_params` are parameters that are supplied (e.g., via @parametrize).
        """
        provided_params = provided_params or {}
        sig = inspect.signature(func)
        kwargs = {}
        for param in sig.parameters:
            if param in provided_params:
                kwargs[param] = provided_params[param]
            else:
                kwargs[param] = self.setup_fixture(param)
        return kwargs

    def setup_fixture(self, name):
        """Setup a fixture and return its value."""
        if name not in FIXTURE_REGISTRY:
            raise ValueError(f"Fixture '{name}' not found or not registered.")

        fixture_info = FIXTURE_REGISTRY[name]
        scope = fixture_info['scope']
        func = fixture_info['func']

        if scope == 'session' and name in self.session_cache:
            return self.session_cache[name]
        
        if scope == 'module' and name in self.module_cache:
            return self.module_cache[name]

        # Fixtures can depend on other fixtures
        kwargs = self.get_fixture_kwargs(func)

        # Execute fixture setup
        if inspect.isgeneratorfunction(func):
            gen = func(**kwargs)
            val = next(gen)
            self.teardowns[scope].append(gen)
        else:
            val = func(**kwargs)

        # Cache if needed
        if scope == 'session':
            self.session_cache[name] = val
        elif scope == 'module':
            self.module_cache[name] = val

        return val

    def teardown_scope(self, scope):
        """Teardown all fixtures for a given scope."""
        for gen in reversed(self.teardowns[scope]):
            try:
                next(gen)
            except StopIteration:
                pass
            except Exception as e:
                print(f"Error during fixture teardown ({scope}): {e}")
        
        self.teardowns[scope] = []
        
        if scope == 'module':
            self.module_cache.clear()
        elif scope == 'session':
            self.session_cache.clear()
