import os

agent_log_path = r"C:\Apps\P2P\clipboard_agent.log"
service_log_path = r"C:\Apps\P2P\service.log"

output_lines = []

if os.path.exists(agent_log_path):
    output_lines.append("=== clipboard_agent.log ===\n")
    with open(agent_log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        output_lines.extend(lines[-100:])
else:
    output_lines.append("clipboard_agent.log does not exist in C:\\Apps\\P2P\n")

if os.path.exists(service_log_path):
    output_lines.append("\n=== service.log ===\n")
    with open(service_log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        output_lines.extend(lines[-100:])
else:
    output_lines.append("service.log does not exist in C:\\Apps\\P2P\n")

with open("scratch/deploy_logs_output.txt", "w", encoding="utf-8") as f:
    f.writelines(output_lines)
