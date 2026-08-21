import json
import os

path = r'C:\Users\Admin\AppData\Roaming\Code\User\globalStorage\sixth.sixth-ai\tasks\1787220775763\api_conversation_history.json'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for msg in data:
    if msg.get('role') == 'assistant' and 'content' in msg:
        content = msg['content']
        if isinstance(content, list):
            for block in content:
                if block.get('type') == 'tool_use':
                    name = block.get('name')
                    args = block.get('input', {})
                    if name in ['write_to_file', 'replace_file_content', 'edit_file']:
                        file_path = args.get('path', args.get('file_path', args.get('TargetFile', '')))
                        print(f"Tool {name} on {file_path}")
                        if 'db.py' in file_path or 'database.py' in file_path or 'auth.py' in file_path or 'assets.py' in file_path or 'jobs.py' in file_path or 'agency.py' in file_path:
                            print(f"Content length: {len(str(args))}")
                elif block.get('type') == 'text':
                    text = block.get('text', '')
                    if 'db.py' in text or 'auth.py' in text or 'assets.py' in text:
                        print("Found mention in text block")
