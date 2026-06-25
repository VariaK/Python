import sys
import time
import multiprocessing
import traceback

from .discovery import load_and_register
from .fixtures import FixtureManager
from .assertions import format_assertion_error

WORKER_FIXTURE_MANAGER = None
WORKER_CURRENT_MODULE = None

def worker_init(conftest_files):
    """Initialize a worker process."""
    global WORKER_FIXTURE_MANAGER
    for path in conftest_files:
        load_and_register(path)
    WORKER_FIXTURE_MANAGER = FixtureManager()

def execute_task(task):
    """Execute a single test task. Run by worker processes or main process."""
    global WORKER_CURRENT_MODULE
    global WORKER_FIXTURE_MANAGER
    
    start_time = time.time()
    
    if task['skip_reason'] is not None:
        return {
            'status': 'SKIP',
            'test_name': task['test_name'],
            'module_path': task['module_path'],
            'time': 0,
            'error_msg': None,
            'reason': task['skip_reason']
        }
        
    status = 'PASS'
    error_msg = None
    
    try:
        # Load module to register any local fixtures and get the test function
        module = load_and_register(task['module_path'])
        
        # Handle module teardown if we switched modules
        if WORKER_CURRENT_MODULE != task['module_path']:
            if WORKER_CURRENT_MODULE is not None:
                WORKER_FIXTURE_MANAGER.teardown_scope('module')
            WORKER_CURRENT_MODULE = task['module_path']
            
        func = getattr(module, task['func_name'])
        
        # Resolve fixtures and parameters
        kwargs = WORKER_FIXTURE_MANAGER.get_fixture_kwargs(func, task['params'])
        
        # Run test
        func(**kwargs)
        
    except AssertionError as e:
        exc_value, _, tb = sys.exc_info()
        error_msg = format_assertion_error(exc_value, tb)
        status = 'FAIL'
    except Exception as e:
        error_msg = traceback.format_exc()
        status = 'FAIL'
    finally:
        # Teardown function-scoped fixtures
        if WORKER_FIXTURE_MANAGER:
            WORKER_FIXTURE_MANAGER.teardown_scope('function')
        
    duration = time.time() - start_time
    
    return {
        'status': status,
        'test_name': task['test_name'],
        'module_path': task['module_path'],
        'time': duration,
        'error_msg': error_msg,
        'reason': None
    }

class TestRunner:
    def __init__(self, parallel=1):
        self.parallel = parallel

    def run(self, tasks, conftest_files):
        """Run all tasks, possibly in parallel."""
        # Sort by module path to group tests from the same module
        tasks.sort(key=lambda t: t['module_path'])
        
        results = []
        if self.parallel > 1:
            # Use multiprocessing pool
            with multiprocessing.Pool(
                processes=self.parallel, 
                initializer=worker_init, 
                initargs=(conftest_files,)
            ) as pool:
                # We use imap or map. map blocks until all are done and preserves order.
                # pool.map returns a list of results in the order of tasks
                results = pool.map(execute_task, tasks)
        else:
            # Sequential
            worker_init(conftest_files)
            for task in tasks:
                results.append(execute_task(task))
                
            # Cleanup global scopes
            global WORKER_FIXTURE_MANAGER
            if WORKER_FIXTURE_MANAGER:
                WORKER_FIXTURE_MANAGER.teardown_scope('module')
                WORKER_FIXTURE_MANAGER.teardown_scope('session')
                
        return results
