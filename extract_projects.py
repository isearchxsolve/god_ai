import re
from collections import defaultdict

with open('D:/omniroute-monetizer/MASTER_WORKLOG.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

projects = defaultdict(list)
for line in lines:
    matches = re.findall(r'`([a-zA-Z]:\\[^`]+)`', line)
    for match in matches:
        projects[match].append(line.strip())

print(f"Total Unique Projects Found: {len(projects)}")
for p, log_lines in projects.items():
    print(f'Project: {p}')
    print(f'  First mention: {log_lines[0]}')
    print(f'  Last log: {log_lines[-1]}')
    print('-' * 40)
