import os
import sys
import importlib.util
import itertools
from .fixtures import register_fixture

def load_module_from_path(path):
    """Dynamically load a python module from a file path."""
    module_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def load_and_register(path):
    """Load module and register any fixtures inside it."""
    module = load_module_from_path(path)
    if not module:
        return None
    for name in dir(module):
        func = getattr(module, name)
        if callable(func) and getattr(func, "__is_fixture__", False):
            register_fixture(name, func, getattr(func, "__fixture_scope__", "function"))
    return module

def generate_parameter_combinations(parametrize_marks):
    """
    Generate a list of kwargs dictionaries from parametrize marks.
    parametrize_marks is a list of tuples: (argnames_str, argvalues_iterable)
    """
    if not parametrize_marks:
        return [{}]
        
    all_param_sets = []
    for argnames, argvalues in parametrize_marks:
        names = [n.strip() for n in argnames.split(',')]
        current_sets = []
        for val in argvalues:
            if len(names) == 1:
                val_tuple = (val,)
            else:
                val_tuple = tuple(val)
            current_sets.append(dict(zip(names, val_tuple)))
        all_param_sets.append(current_sets)
        
    # Cartesian product for stacked decorators
    combinations = []
    for combo in itertools.product(*all_param_sets):
        merged = {}
        for d in combo:
            merged.update(d)
        combinations.append(merged)
        
    return combinations

def discover_tests(start_dir):
    """
    Traverse directory, load test modules, register fixtures, and collect test tasks.
    Returns: (tasks, conftest_files)
    """
    test_files = []
    conftest_files = []
    
    # Traverse directory
    for root, _, files in os.walk(start_dir):
        for file in files:
            if file == "conftest.py":
                conftest_files.append(os.path.abspath(os.path.join(root, file)))
            elif file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.abspath(os.path.join(root, file)))
                
    # Load conftests first
    for path in conftest_files:
        load_and_register(path)
        
    tasks = []
    
    # Discover tests
    for path in test_files:
        module = load_and_register(path)
        if not module:
            continue
            
        for name in dir(module):
            func = getattr(module, name)
            if not callable(func):
                continue
                
            is_test = name.startswith("test_") or getattr(func, "__is_test__", False)
            if is_test:
                skip_reason = getattr(func, "__skip_reason__", None)
                parametrize_marks = getattr(func, "__parametrize__", [])
                
                param_combinations = generate_parameter_combinations(parametrize_marks)
                
                for params in param_combinations:
                    test_name = name
                    if params:
                        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
                        test_name = f"{name}[{param_str}]"
                        
                    tasks.append({
                        'module_path': path,
                        'module_name': module.__name__,
                        'func_name': name,
                        'test_name': test_name,
                        'params': params,
                        'skip_reason': skip_reason
                    })
                    
    return tasks, conftest_files
