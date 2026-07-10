import sys

with open('windows_service_loop.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.startswith('def spawn_gui_agent(session_id):'):
        skip = True
        continue
    if skip and line.startswith('def trigger_sas_system():'):
        skip = False
        
    if skip:
        continue
        
    if 'gui_agent_pid' in line:
        continue
            
    if '# Spawn or check GUI Agent' in line:
        skip = True
        continue
    
    if skip and 'except Exception as e:' in line and 'Lỗi trong vòng lặp chính' in lines[i+1]:
        skip = False
        
    if skip:
        continue
        
    new_lines.append(line)

with open('windows_service_loop.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Patched.")
