import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

search_update = """    def update_progress(self, sent_bytes):
        percent = int(sent_bytes * 100 / self.total_size) if self.total_size > 0 else 100
        percent = max(0, min(100, percent))

        self.prog1["value"] = percent
        self.prog2["value"] = percent

        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0 and sent_bytes > 0:
            speed = sent_bytes / elapsed_time
            if speed > 0:
                remaining_bytes = self.total_size - sent_bytes
                remaining_time = remaining_bytes / speed
                mins = int(remaining_time // 60)
                secs = int(remaining_time % 60)
                if mins > 0:
                    time_str = f"{mins} min {secs} sec(s)"
                else:
                    time_str = f"{secs} sec(s)"
            else:
                time_str = "-- sec(s)"
            speed_str = f"{self.format_speed(speed)}"
        else:
            speed_str = "-- MB/s"
            time_str = "-- sec(s)"

        sent_str = self.format_size(sent_bytes)
        
        self.lbl_stats1.config(text=f"({sent_str} of {self.format_size(self.total_size)})  {speed_str}  {time_str}")
        self.lbl_stats2.config(text=f"{sent_str} of {self.format_size(self.total_size)}  {time_str}")
        
        self.update_idletasks()"""

replace_update = """    def update_progress(self, sent_bytes):
        def _do_update():
            try:
                percent = int(sent_bytes * 100 / self.total_size) if self.total_size > 0 else 100
                percent = max(0, min(100, percent))

                self.prog1["value"] = percent
                self.prog2["value"] = percent

                elapsed_time = time.time() - self.start_time
                if elapsed_time > 0 and sent_bytes > 0:
                    speed = sent_bytes / elapsed_time
                    if speed > 0:
                        remaining_bytes = self.total_size - sent_bytes
                        remaining_time = remaining_bytes / speed
                        mins = int(remaining_time // 60)
                        secs = int(remaining_time % 60)
                        if mins > 0:
                            time_str = f"{mins} min {secs} sec(s)"
                        else:
                            time_str = f"{secs} sec(s)"
                    else:
                        time_str = "-- sec(s)"
                    speed_str = f"{self.format_speed(speed)}"
                else:
                    speed_str = "-- MB/s"
                    time_str = "-- sec(s)"

                sent_str = self.format_size(sent_bytes)
                
                self.lbl_stats1.config(text=f"({sent_str} of {self.format_size(self.total_size)})  {speed_str}  {time_str}")
                self.lbl_stats2.config(text=f"{sent_str} of {self.format_size(self.total_size)}  {time_str}")
            except: pass
        try:
            self.after(0, _do_update)
        except: pass
        
    def safe_destroy(self):
        try: self.after(0, self.destroy)
        except: pass"""

if search_update in content:
    content = content.replace(search_update, replace_update)
    print("Replaced update_progress")
else:
    print("Not found update_progress")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
