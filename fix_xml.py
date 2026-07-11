with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

insert_idx = -1
for i, line in enumerate(lines):
    if 'os.chdir(app_dir)' in line:
        insert_idx = i + 1
        break

if insert_idx != -1:
    code = """
def get_computers_xml_path():
    import os, sys
    installed_path = r"C:\\Apps\\P2P\\saved_computers.xml"
    if os.path.exists(installed_path):
        return installed_path
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "saved_computers.xml")
"""
    lines.insert(insert_idx, code)

for i in range(len(lines)):
    if 'new_xml_file = "saved_computers.xml"' in lines[i]:
        lines[i] = lines[i].replace('"saved_computers.xml"', 'get_computers_xml_path()')
    elif 'computers_file = "saved_computers.xml"' in lines[i]:
        lines[i] = lines[i].replace('"saved_computers.xml"', 'get_computers_xml_path()')

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
