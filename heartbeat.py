import re

file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(file, 'r', encoding='utf-8') as f:
    text = f.read()

loop_logic = """                    val frameInfo = TcpStreamManager.instance?.waitForNextFrame(lastSeenId, 2000L)
                    if (frameInfo != null) {
                        lastSeenId = frameInfo.first
                        val jpegBytes = frameInfo.second
                        sendEncryptedData(s, jpegBytes)
                        consecutiveRefreshCount = 0  // Reset counter khi cA3 frame thAnh cA'ng
                    } else {
                        // HEARTBEAT RESEND: Nu Viewer b l> frame 'u tiAn (do mng hoc render li),
                        // chAAng ta gi li frame c sau mi 2 giAy cho d mAn hAnh khA'ng 'i
                        val cachedJpeg = TcpStreamManager.instance?.getFrameJpeg()
                        if (cachedJpeg != null) {
                            Log.d(TAG, "No new frame. Resending cached frame (Heartbeat)...")
                            sendEncryptedData(s, cachedJpeg)
                        } else {
                            consecutiveRefreshCount++
                            if (consecutiveRefreshCount <= MAX_CONSECUTIVE_REFRESH) {
                                // Fix for black screen on lock/unlock: force a refresh if the frame is stuck
                                Log.d(TAG, "No frame, forceRefresh attempt $consecutiveRefreshCount/$MAX_CONSECUTIVE_REFRESH")
                                TcpStreamManager.instance?.forceRefresh()
                            } else {
                                if (consecutiveRefreshCount == MAX_CONSECUTIVE_REFRESH + 1) {
                                    Log.w(TAG, "Max forceRefresh reached. Waiting for frame without refresh...")
                                }
                            }
                        }
                    }"""

text = re.sub(r'                    val frameInfo = TcpStreamManager\.instance\?\.waitForNextFrame\(lastSeenId, 2000L\).*?if \(consecutiveRefreshCount == MAX_CONSECUTIVE_REFRESH \+ 1\) \{\n\s*Log\.w\(TAG, "Max forceRefresh reached\. Waiting for frame without refresh\.\.\."\)\n\s*\}\n\s*\}\n\s*\}', loop_logic, text, flags=re.DOTALL)

with open(file, 'w', encoding='utf-8') as f:
    f.write(text)