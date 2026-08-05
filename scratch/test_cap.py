import sys
import time

class MultiCapCtx:
    def __init__(self):
        self.use_dxcam = False
        self.dxcam_camera = None
        self.sct = None
    def __enter__(self):
        if sys.platform == "win32":
            try:
                import dxcam
                self.dxcam_camera = dxcam.create(output_color="BGR")
                if self.dxcam_camera is not None:
                    self.dxcam_camera.start(video_mode=True)
                    self.use_dxcam = True
            except Exception as e:
                print(f"DXCam fallback: {e}")
        if not self.use_dxcam:
            import mss
            self.sct = mss.mss()
            self.sct.__enter__()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.use_dxcam and self.dxcam_camera:
            self.dxcam_camera.stop()
        elif self.sct:
            self.sct.__exit__(exc_type, exc_val, exc_tb)

def test():
    with MultiCapCtx() as cap_ctx:
        use_dxcam = cap_ctx.use_dxcam
        dxcam_camera = cap_ctx.dxcam_camera
        sct = cap_ctx.sct
        
        print("Using dxcam:", use_dxcam)
        for _ in range(5):
            if use_dxcam:
                frame = dxcam_camera.get_latest_frame()
                if frame is not None:
                    print("DXCam Frame:", frame.shape)
            else:
                if len(sct.monitors) > 1:
                    mon = sct.monitors[1]
                else:
                    mon = sct.monitors[0]
                img = sct.grab(mon)
                print("MSS Frame:", img.size)
            time.sleep(0.1)

if __name__ == "__main__":
    test()
