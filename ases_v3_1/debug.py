import sys
sys.path.insert(0, 'agent_service')
print('Sys path:', sys.path[:3])
try:
    import interaction_reviewer
    print('Module imported')
    print('Dir:', [x for x in dir(interaction_reviewer) if not x.startswith('_')])
    # Try to get the function
    func = getattr(interaction_reviewer, '_run_single_test', None)
    print('_run_single_test:', func)
    if func:
        print('Type:', type(func))
    else:
        print('Not found in dir')
        # Let's see what's in the module's __dict__
        print('Keys in __dict__:', list(interaction_reviewer.__dict__.keys()))
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()
