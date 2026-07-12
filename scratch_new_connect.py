        sock = None
        connected = False
        handshake_done = False
        cached_res_payload = None
        force_relay = getattr(self, '_current_force_relay', False)

        # ====== BƯỚC 1: Quét mạng LAN để tìm ID (5 lần) ======
        lan_target = None
        if not force_relay and hasattr(self, 'lan_peers'):
            for attempt in range(5):
                self.update_status(_("Đang tìm máy trong mạng LAN (lần {n}/5)...").format(n=attempt + 1))
                current_time = time.time()
                with self.lan_peers_lock:
                    # Clean up old peers
                    self.lan_peers = {k: v for k, v in self.lan_peers.items() if current_time - v.get("last_seen", 0) < 15}
                    if partner_id in self.lan_peers:
                        lan_target = self.lan_peers[partner_id]
                
                if lan_target:
                    print(f"[LAN Discovery] Tìm thấy đối tác {partner_id} trong mạng LAN!")
                    break
                
                time.sleep(1.0) # Đợi 1s giữa các lần tìm

        if lan_target:
            self.update_status(_("Đang thử kết nối LAN trực tiếp..."))
            local_ip = lan_target.get("local_ip", "")
            local_port = lan_target.get("port", 12345)
            ips_to_try = [ip.strip() for ip in local_ip.split(',') if ip.strip()]
            ports_to_try = [local_port]
            for p in [12345, 12346, 12347, 12348]:
                if p not in ports_to_try:
                    ports_to_try.append(p)
            
            for try_ip in ips_to_try:
                if connected: break
                for p in ports_to_try:
                    if connected: break
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(1.0)
                        s.connect((try_ip, p))
                        s.settimeout(2.0)
                        # Handshake
                        socket_passwords[s] = partner_pass
                        import platform
                        hs_data = json.dumps({"password": partner_pass, "client_id": self.my_id_clean, "computer_name": platform.node()}).encode('utf-8')
                        send_msg(s, hs_data, partner_pass)
                        tmp_res_msg = recv_msg(s, [partner_pass, APP_KEY])
                        if tmp_res_msg:
                            tmp_res = json.loads(tmp_res_msg.decode('utf-8'))
                            if tmp_res.get("status") in ("ok", "error"):
                                sock = s
                                connected = True
                                handshake_done = True
                                cached_res_payload = tmp_res
                                print(f"[Client] Connected & Handshaked via LAN Direct: {try_ip}:{p}")
                                break
                        if not connected:
                            force_close_socket(s)
                    except Exception:
                        try: s.close()
                        except: pass
        
        # ====== BƯỚC 2: Hỏi Signaling Server (nếu LAN thất bại hoặc không tìm thấy) ======
        public_ip, port = None, None
        specific_host = getattr(self, 'current_signaling_host', None)
        
        if not connected:
            if not hasattr(self, 'signaling_sockets') or not self.signaling_sockets:
                self.update_status(_("Chưa kết nối Signaling Server!"))
                self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Chưa kết nối đến Server Báo hiệu. Vui lòng kiểm tra lại mạng.")))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                return

            req = json.dumps({
                "action": "connect_request",
                "target": partner_id,
                "port": BOUND_PORT,
                "local_ip": getattr(self, 'local_ip', "127.0.0.1"),
                "local_port": BOUND_PORT
            }) + '\n'
            
            sockets_to_try = []
            with self.signaling_lock:
                if getattr(self, 'primary_signaling_socket', None):
                    sockets_to_try.append(self.primary_signaling_socket)
                for s in getattr(self, 'signaling_sockets', {}).values():
                    if s not in sockets_to_try:
                        sockets_to_try.append(s)
                        
            self.update_status(_("Đang tìm địa chỉ đối tác trên server danh bạ..."))
            
            signaling_success = False
            for s in sockets_to_try:
                self.pending_connection_info = None
                try:
                    with self.signaling_lock:
                        send_msg(s, req.encode('utf-8'), APP_KEY)
                except Exception:
                    continue
                    
                wait_timeout = 6.0
                while wait_timeout > 0 and self.pending_connection_info is None:
                    time.sleep(0.2)
                    wait_timeout -= 0.2
                    
                if self.pending_connection_info and self.pending_connection_info != "error":
                    signaling_success = True
                    break
                    
            if not signaling_success:
                if reconnect_queue and retry_count < 30:
                    self.update_status(_("Mất kết nối. Đang thử kết nối lại lần {count}/30...").format(count=retry_count + 1))
                    time.sleep(2)
                    self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid)
                    return
                self.update_status(_("Sẵn sàng kết nối"))
                if not reconnect_queue:
                    self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Không thể tìm thấy hoặc đối tác đang Offline.")))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                if reconnect_queue:
                    reconnect_queue.put("FAILED")
                return
                
            if len(self.pending_connection_info) >= 4:
                public_ip, port_str, _, _ = self.pending_connection_info[:4]
            else:
                public_ip, port_str, _ = self.pending_connection_info
                
            port = int(port_str) if port_str else 0

        # ====== BƯỚC 3: Đục lỗ Tường lửa (TCP Hole Punching) 10 lần ======
        if not connected and not force_relay and public_ip and port:
            skip_hole_punch = False
            if hasattr(self, 'current_ip') and self.current_ip == public_ip:
                print("[Client] Skipping Hole Punching because both peers share the same Public IP (same router).")
                skip_hole_punch = True
            
            if not skip_hole_punch:
                self.update_status(_("Đang đục lỗ Tường lửa tới {ip}:{port}...").format(ip=public_ip, port=port))
                
                if getattr(self, 'server_socket', None):
                    try: self.server_socket.close()
                    except: pass
                
                for attempt in range(10):
                    self.update_status(_("Đang đục lỗ Tường lửa lần {n}/10...").format(n=attempt + 1))
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try: s.bind(('0.0.0.0', BOUND_PORT))
                    except: pass
                    s.settimeout(0.5)
                    try:
                        s.connect((public_ip, port))
                        connected = True
                        sock = s
                        print(f"[Client] Hole punch successful!")
                        break
                    except Exception:
                        force_close_socket(s)
                        time.sleep(0.1)
                        
                # Phục hồi server_socket
                try:
                    try:
                        if hasattr(socket, 'AF_INET6'):
                            self.server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            if hasattr(socket, 'IPPROTO_IPV6') and hasattr(socket, 'IPV6_V6ONLY'):
                                try: self.server_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                                except: pass
                            self.server_socket.bind(("", BOUND_PORT))
                        else:
                            raise Exception("No IPv6")
                    except Exception:
                        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        self.server_socket.bind(('0.0.0.0', BOUND_PORT))
                    self.server_socket.listen(5)
                except Exception as e:
                    pass

        # ====== BƯỚC 4: Server Trung Chuyển (Relay) Fallback ======
        if not connected:
            display_host = specific_host or 'Relay'
            self.update_status(_("Đục lỗ/LAN thất bại. Đang thử kết nối qua Server Trung Chuyển ({host})...").format(host=display_host))
            try:
                relay_session_id = f"relay_{self.my_id_clean}_{partner_id}"
                relay_req = json.dumps({
                    "action": "relay_request",
                    "target": partner_id,
                    "session_id": relay_session_id,
                    "relay_host": specific_host
                }) + '\n'
                with self.signaling_lock:
                    if getattr(self, 'primary_signaling_socket', None):
                        send_msg(self.primary_signaling_socket, relay_req.encode('utf-8'), APP_KEY)
                    else:
                        raise Exception("Chưa kết nối tới Signaling Server!")
                
                host_to_connect = specific_host if specific_host else core.config.SIGNALING_SERVER_HOSTS[0]
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5.0)
                s.connect((host_to_connect, core.config.SIGNALING_SERVER_PORT))
                s.settimeout(None)
                header = f"RELAY_CLIENT:{relay_session_id}\n"
                s.sendall(header.encode('utf-8'))
                
                time.sleep(1.5)
                sock = s
                connected = True
                self.update_status(_("Đã kết nối qua Relay Server!"))
            except Exception as e:
                connected = False

        if not connected:
            self.update_status(_("Sẵn sàng kết nối"))
            self.after(0, lambda: self.show_custom_error(_("Lỗi kết nối"), _("Không thể kết nối (LAN, Đục lỗ, Relay đều thất bại).")))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock: force_close_socket(sock)
            return

        # ======================================================================
        # Hoàn tất kết nối và handshake
        # ======================================================================
