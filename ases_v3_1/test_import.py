import sys
sys.path.insert(0, 'agent_service')
import interaction_reviewer
print("Module loaded:", interaction_reviewer.__name__)
print("Dir:", [x for x in dir(interaction_reviewer) if not x.startswith('__')])
print("Has _run_single_test:", hasattr(interaction_reviewer, '_run_single_test'))
if hasattr(interaction_reviewer, '_run_single_test'):
    print("Function:", interaction_reviewer._run_single_test)
