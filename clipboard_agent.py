"""
Clipboard Agent Wrapper - Chạy ở quyền User thường.
Chỉ đơn giản là gọi hàm run_clipboard_agent_mode() từ app.py để tránh trùng lặp code và xung đột.
"""

import sys
import os

# Đảm bảo import được app.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Đảm bảo tham số --clipboard-agent có trong sys.argv để app.py biết đang chạy ở chế độ agent
    if "--clipboard-agent" not in sys.argv:
        sys.argv.append("--clipboard-agent")
        
    import app
    app.run_clipboard_agent_mode()
