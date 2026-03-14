import tkinter as tk
from tkinter import font, ttk, filedialog, messagebox
import paho.mqtt.client as mqtt
from datetime import datetime
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import math
import matplotlib.ticker as ticker
import os 
import sys
import requests 
import csv 

# --- MQTT 設定 ---
MQTT_SERVER = "mqttgo.io"
SUB_TOPICS = [("wokwi/dht/temperature", 0), ("wokwi/dht/humidity", 0)]
PUB_TOPIC = "wokwi/led/control"

try:
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
    plt.rcParams['axes.unicode_minus'] = False 
except:
    pass

class DashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NCUT 勤益科大 - 作業1  MQTT_Python Tkinter + Discord_Webhook")
        self.root.geometry("800x740")  
        self.root.configure(bg="#1a1a1a") 

        self.discord_webhook_url = "https://discord.com/api/webhooks/1479511939666153647/ZUNGk0_42Z6VO-xeWaBfQ_lQhDh9QRXBs3f_h1zJHVIt-vl6-Xrk-EL3TV3Sk9yT3kN0"
        self.last_discord_send_time = 0  
        self.discord_interval = 20       

        # 狀態控制標籤
        self.is_running = True 
        self.mqtt_connected = False 
        self.last_msg_time = 0 
        self.wifi_tick = 0 
        
        self.has_new_data = False 

        self.target_t = 0.0  
        self.target_h = 0.0  
        self.anim_t = 0.0    
        self.anim_h = 0.0    
        self.wave_offset = 0 

        self.max_points = 200 
        self.temp_history = deque(maxlen=self.max_points)
        self.humd_history = deque(maxlen=self.max_points)
        self.time_history = deque(maxlen=self.max_points)

        self.setup_ui()
        self.setup_mqtt()
        
        self.animate_icons()
        self.update_clock_and_chart()

    def setup_ui(self):
        # --- 頂部資訊列 ---
        top_container = tk.Frame(self.root, bg="#2c3e50", pady=8, padx=15)
        top_container.pack(fill=tk.X)
        
        self.label_font = font.Font(family="Microsoft JhengHei", size=13, weight="bold")
        info_str = "國立勤益科大 / 產攜電訓三甲 / DB212211 / 詹景翔"
        tk.Label(top_container, text=info_str, font=self.label_font, fg="#ffffff", bg="#2c3e50").pack(side=tk.LEFT)

        self.control_frame = tk.Frame(top_container, bg="#2c3e50")
        self.control_frame.pack(side=tk.RIGHT)
        
        self.sys_status_label = tk.Label(self.control_frame, text="系統狀態: 連線中...", font=("Microsoft JhengHei", 11, "bold"), fg="#f1c40f", bg="#2c3e50")
        self.sys_status_label.pack(side=tk.LEFT, padx=(0, 15))

        tk.Button(self.control_frame, text="離開", width=6, bg="#c0392b", fg="white", font=("Microsoft JhengHei", 10, "bold"), command=self.exit_app).pack(side=tk.LEFT, padx=(15, 0))

        # --- 分頁系統 ---
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background="#1a1a1a", borderwidth=0)
        style.configure("TNotebook.Tab", background="#34495e", foreground="white", padding=[15, 5], font=("Microsoft JhengHei", 12, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#2980b9")])

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 10))

        self.tab_dash = tk.Frame(self.notebook, bg="#1a1a1a")
        self.tab_led = tk.Frame(self.notebook, bg="#1a1a1a")

        self.notebook.add(self.tab_dash, text="溫溼度儀錶板")
        self.notebook.add(self.tab_led, text="LED 控制面板")

        # --- 分頁 1: 溫溼度儀表板 ---
        led_panel = tk.Frame(self.tab_dash, bg="#080808", bd=3, relief="solid", highlightbackground="#555555", highlightthickness=3, width=860, height=260)
        led_panel.pack(pady=(15, 10))
        led_panel.pack_propagate(False) 

        status_bar = tk.Frame(led_panel, bg="#080808")
        status_bar.pack(fill=tk.X, pady=(10, 0))
        
        self.time_font = font.Font(family="Microsoft JhengHei", size=24, weight="bold")
        self.time_label = tk.Label(status_bar, text="", font=self.time_font, fg="#FFFFFF", bg="#080808")
        self.time_label.pack(side=tk.LEFT, padx=30, pady=0)
        
        self.canvas_wifi = tk.Canvas(status_bar, width=50, height=45, bg="#080808", highlightthickness=0)
        self.canvas_wifi.pack(side=tk.RIGHT, padx=30, pady=0)

        self.led_font = font.Font(family="Arial Rounded MT Bold", size=65, weight="bold")
        self.unit_font = font.Font(family="Microsoft JhengHei", size=22, weight="bold")
        self.prefix_font = font.Font(family="Microsoft JhengHei", size=22, weight="bold")

        for canvas_attr, val_attr, prefix, color, unit in [
            ("canvas_t", "temp_val_label", "溫度: ", "#FF0000", "°C"),
            ("canvas_h", "humd_val_label", "濕度: ", "#0088FF", "% RH")
        ]:
            frame = tk.Frame(led_panel, bg="#080808")
            frame.pack(fill=tk.X, pady=0)
            cv = tk.Canvas(frame, width=80, height=90, bg="#080808", highlightthickness=0)
            cv.pack(side=tk.LEFT, padx=(30, 10))
            setattr(self, canvas_attr, cv)
            tk.Label(frame, text=prefix, font=self.prefix_font, fg="#FFFFFF", bg="#080808").pack(side=tk.LEFT)
            val_lb = tk.Label(frame, text=" N/A ", font=self.led_font, fg=color, bg="#080808", width=5, anchor="e")
            val_lb.pack(side=tk.LEFT)
            setattr(self, val_attr, val_lb)
            uf = tk.Frame(frame, bg="#080808")
            uf.pack(side=tk.RIGHT, padx=(0, 30), pady=(15,0))
            tk.Label(uf, text=unit, font=self.unit_font, fg="#FFFFFF", bg="#080808").pack(anchor="e")

        self.chart_frame = tk.Frame(self.tab_dash, bg="#1a1a1a")
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))
        self.setup_charts()

        export_frame = tk.Frame(self.tab_dash, bg="#1a1a1a")
        export_frame.pack(fill=tk.X, padx=25, pady=(0, 10))
        btn_csv = tk.Button(export_frame, text="匯出歷史報表(.csv)", font=("Microsoft JhengHei", 12, "bold"), bg="#2980b9", fg="white", cursor="hand2", command=self.export_csv)
        btn_csv.pack(side=tk.RIGHT)

        # --- 分頁 2: LED 控制面板 ---
        title_lbl = tk.Label(self.tab_led, text=" LED控制與指令 ", font=("Microsoft JhengHei", 24, "bold"), fg="#000000", bg="#4d4d4d")
        title_lbl.pack(pady=(20, 10))

        grid_frame = tk.Frame(self.tab_led, bg="#2c3e50", bd=2, relief="ridge", padx=20, pady=10)
        grid_frame.pack(pady=5)

        targets = [("全域控制 (ALL)", "all"), ("LED 1", "1"), ("LED 2", "2"), ("LED 3", "3"), ("LED 4", "4")]
        actions = [("打開 (ON)", "on", "#c0392b"), ("關閉 (OFF)", "off", "#27ae60"), ("閃爍 (FLASH)", "flash", "#2802ff"), ("計時 5s", "timer", "#7b8802")]

        for r, (label_text, target_val) in enumerate(targets):
            lbl = tk.Label(grid_frame, text=label_text, font=("Microsoft JhengHei", 14, "bold"), fg="white", bg="#2c3e50", width=15, anchor="e")
            lbl.grid(row=r, column=0, padx=10, pady=8)
            for c, (act_text, act_val, color) in enumerate(actions):
                btn = tk.Button(grid_frame, text=act_text, font=("Arial", 11, "bold"), bg=color, fg="white", 
                                activebackground="#ecf0f1", activeforeground="black", width=12, height=1, cursor="hand2",
                                command=lambda t=target_val, a=act_val: self.send_led_cmd(t, a))
                btn.grid(row=r, column=c+1, padx=6, pady=5)

        chat_container = tk.Frame(self.tab_led, bg="#1a1a1a")
        chat_container.pack(fill=tk.BOTH, expand=True, padx=40, pady=(10, 20))

        tk.Label(chat_container, text="指令視窗", font=("Microsoft JhengHei", 12, "bold"), fg="#bdc3c7", bg="#1a1a1a").pack(anchor="w")

        self.chat_log = tk.Text(chat_container, height=6, bg="#0d0d0d", fg="#2ecc71", font=("Consolas", 12), state=tk.DISABLED, bd=2, relief="sunken")
        self.chat_log.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        self.chat_log.tag_config('recv', foreground='#3498db') 

        input_frame = tk.Frame(chat_container, bg="#1a1a1a")
        input_frame.pack(fill=tk.X)

        self.cmd_entry = tk.Entry(input_frame, font=("Consolas", 14), bg="#34495e", fg="white", insertbackground="white")
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.cmd_entry.bind("<Return>", self.send_manual_cmd) 

        send_btn = tk.Button(input_frame, text="送出指令", font=("Microsoft JhengHei", 12, "bold"), bg="#8e44ad", fg="white", cursor="hand2", command=self.send_manual_cmd)
        send_btn.pack(side=tk.RIGHT, padx=(10, 0), ipadx=10, ipady=2)

    def setup_charts(self):
        self.fig, (self.ax_t, self.ax_h) = plt.subplots(1, 2, figsize=(9.0, 3.2))
        self.fig.patch.set_facecolor('#aaaaaa')
        for ax in [self.ax_t, self.ax_h]:
            ax.set_facecolor('#e8e8e8')
            ax.yaxis.set_major_locator(ticker.MultipleLocator(10))
            ax.grid(True, axis='y', linestyle='--', alpha=0.6)
            
        self.line_t, = self.ax_t.plot([], [], color='#FF0000', linewidth=2.5, marker='o')
        self.line_h, = self.ax_h.plot([], [], color='#0066FF', linewidth=2.5, marker='o')
        
        # 🌟 初始動態標題
        self.ax_t.set_title("等待溫度資料...", fontsize=13, fontweight='bold', pad=10)
        self.ax_h.set_title("等待濕度資料...", fontsize=13, fontweight='bold', pad=10)

        self.fig.subplots_adjust(wspace=0.22, top=0.80, bottom=0.25, left=0.08, right=0.96)
        
        self.canvas_chart = FigureCanvasTkAgg(self.fig, master=self.chart_frame)
        self.canvas_chart.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def setup_mqtt(self):
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except AttributeError:
            self.client = mqtt.Client()
            
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        
        try:
            self.client.connect(MQTT_SERVER, 1883, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"❌ MQTT 連線失敗: {e}")

    def on_connect(self, client, userdata, flags, rc, *args):
        if rc == 0:
            self.mqtt_connected = True
            for topic, qos in SUB_TOPICS:
                client.subscribe(topic)

    def on_disconnect(self, client, userdata, rc, *args):
        self.mqtt_connected = False

    def on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode()
            val = float(payload_str)
            self.last_msg_time = time.time() # 🌟 更新心跳時間
            
            if msg.topic == "wokwi/dht/temperature":
                self.target_t = val
                self.temp_val_label.config(text=f"{val:5.1f}", fg=("#0088FF" if val < 0 else "#FF0000"))
                self.has_new_data = True 
                
            elif msg.topic == "wokwi/dht/humidity":
                self.target_h = val
                self.humd_val_label.config(text=f"{val:5.1f}")
                self.has_new_data = True 
                
        except ValueError:
            pass
        except Exception as e:
            pass

    def log_chat(self, msg, is_recv=False):
        self.chat_log.config(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = "[接收]" if is_recv else "[發布]"
        tag = 'recv' if is_recv else None
        
        self.chat_log.insert(tk.END, f"[{ts}] {prefix} {msg}\n", tag)
        self.chat_log.see(tk.END) 
        self.chat_log.config(state=tk.DISABLED)

    def send_led_cmd(self, target, action):
        if not self.mqtt_connected: 
            self.log_chat("⚠️ 伺服器已斷線，無法發送", False)
            return
            
        cmd_str = f"{target}{action}" 
        self.client.publish(PUB_TOPIC, cmd_str)
        self.log_chat(f"按下按鈕: {cmd_str.upper()}", False)

    def send_manual_cmd(self, event=None):
        if not self.mqtt_connected: 
            self.log_chat("⚠️ 伺服器已斷線，無法發送", False)
            return
        
        cmd_str = self.cmd_entry.get().strip() 
        if cmd_str: 
            self.client.publish(PUB_TOPIC, cmd_str)
            self.log_chat(f"手動指令: {cmd_str}", False)
            self.cmd_entry.delete(0, tk.END) 

    def export_csv(self):
        if len(self.temp_history) == 0:
            messagebox.showwarning("警告", "目前沒有接收到溫溼度資料可以匯出！")
            return
        
        default_filename = f"SensorData_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV 檔案", "*.csv"), ("所有檔案", "*.*")], title="匯出歷史報表", initialfile=default_filename)
        
        if filepath:
            try:
                with open(filepath, mode='w', newline='', encoding='utf-8-sig') as file:
                    writer = csv.writer(file)
                    writer.writerow(["紀錄時間", "溫度 (°C)", "濕度 (% RH)"]) 
                    for t_time, t_temp, t_humd in zip(self.time_history, self.temp_history, self.humd_history):
                        writer.writerow([t_time, f"{t_temp:.1f}", f"{t_humd:.1f}"])
                messagebox.showinfo("匯出成功", f"資料已成功儲存至：\n{filepath}")
            except Exception as e:
                messagebox.showerror("匯出失敗", f"寫入檔案時發生錯誤：\n{e}")

    def send_to_discord(self, temp, humd):
        if not self.discord_webhook_url or "這裡貼上" in self.discord_webhook_url: return 
        content = f"**ESP32溫溼度 回報**\n 溫度: `{temp:.1f} °C`\n 濕度: `{humd:.1f} % RH`\n 紀錄時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        data = { "content": content, "username": "MQTT_Python Tkinter" }
        try: requests.post(self.discord_webhook_url, json=data, timeout=3)
        except: pass

    def exit_app(self):
        self.is_running = False 
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except: pass
        self.root.after(200, lambda: os._exit(0))

    def update_clock_and_chart(self):
        if not self.is_running: return
        
        now = datetime.now()
        now_str = now.strftime("%H:%M:%S")
        self.time_label.config(text=f"{now.year} 年 {now.month:02d} 月 {now.day:02d} 日   {now.strftime('%H')} 時 : {now.strftime('%M')} 分 : {now.strftime('%S')} 秒")

        # 🌟 完美的雙重斷線偵測
        if self.mqtt_connected:
            # 判斷是否 15 秒內有收到 ESP32 的心跳包或資料
            if time.time() - self.last_msg_time < 15.0:
                self.sys_status_label.config(text="連線狀態:ESP32/MQTT已連線", fg="#2ecc71")
            else:
                # 只有在曾經收過資料，然後突然中斷時才顯示警告
                if self.last_msg_time > 0:
                    self.sys_status_label.config(text="連線狀態:ESP32 已離線", fg="#f39c12")
                else:
                    self.sys_status_label.config(text="連線狀態:等待ESP32 連線中...", fg="#f1c40f")
        else:
            self.sys_status_label.config(text="連線狀態:MQTT 連線中...", fg="#e74c3c")

        # 🌟 收到新資料時更新圖表與標題
        if getattr(self, 'has_new_data', False):
            self.has_new_data = False 
            
            if len(self.temp_history) == 0 or self.target_t != self.temp_history[-1] or self.target_h != self.humd_history[-1]:
                
                self.temp_history.append(self.target_t)
                self.humd_history.append(self.target_h)
                self.time_history.append(now_str)

                # 🌟 更新動態圖表標題
                self.ax_t.set_title(f"目前溫度: {self.target_t:.1f} °C", fontsize=13, fontweight='bold', pad=10)
                self.ax_h.set_title(f"目前濕度: {self.target_h:.1f} % RH", fontsize=13, fontweight='bold', pad=10)

                current_time = time.time()
                if (current_time - self.last_discord_send_time) >= self.discord_interval:
                    self.last_discord_send_time = current_time
                    self.send_to_discord(self.target_t, self.target_h)

                display_points = 10
                t_data = list(self.temp_history)[-display_points:]
                h_data = list(self.humd_history)[-display_points:]
                time_labels = list(self.time_history)[-display_points:]

                self.line_t.set_ydata(t_data)
                self.line_t.set_xdata(range(len(t_data)))
                self.line_h.set_ydata(h_data)
                self.line_h.set_xdata(range(len(h_data)))
                
                self.ax_t.set_xticks(range(len(time_labels)))
                self.ax_t.set_xticklabels(time_labels, rotation=30)
                self.ax_h.set_xticks(range(len(time_labels)))
                self.ax_h.set_xticklabels(time_labels, rotation=30)
                
                self.ax_t.relim(); self.ax_t.autoscale_view()
                self.ax_h.relim(); self.ax_h.autoscale_view()
                self.canvas_chart.draw()

        self.root.after(1000, self.update_clock_and_chart)

    def animate_icons(self):
        if not self.is_running: return
        self.anim_t += (self.target_t - self.anim_t) * 0.1
        self.anim_h += (self.target_h - self.anim_h) * 0.1
        self.wave_offset += 0.4; self.wifi_tick += 1 

        self.canvas_t.delete("all")
        t_color = "#0088FF" if self.anim_t < 0 else "#FF0000"
        t_ratio = max(0.0, min(1.0, (self.anim_t + 40) / 120.0))
        fill_y = 75 - (t_ratio * 60)
        self.canvas_t.create_oval(30, 60, 50, 80, fill=t_color, outline="white", width=2)
        self.canvas_t.create_rectangle(37, fill_y, 43, 70, fill=t_color, outline="")
        self.canvas_t.create_line(35, 15, 35, 65, fill="white", width=2); self.canvas_t.create_line(45, 15, 45, 65, fill="white", width=2)
        self.canvas_t.create_arc(35, 10, 45, 20, start=0, extent=180, outline="white", width=2, style=tk.ARC)
        self.canvas_t.create_rectangle(37, 59, 43, 67, fill=t_color, outline="")

        self.canvas_h.delete("all")
        for x in range(20, 61):
            val = 400 - (x - 40)**2
            bottom_y = 60 + math.sqrt(val if val > 0 else 0)
            top_y = 60 - 2.5 * (x - 20) if x < 40 else 10 + 2.5 * (x - 40)
            wave_y = (80 - (self.anim_h / 100.0) * 70) + math.sin(x * 0.2 + self.wave_offset) * 2
            start_y = max(wave_y, top_y)
            if start_y < bottom_y: self.canvas_h.create_line(x, start_y, x, bottom_y, fill="#0088FF")
        self.canvas_h.create_line(40, 10, 20, 60, fill="white", width=2); self.canvas_h.create_line(40, 10, 60, 60, fill="white", width=2)
        self.canvas_h.create_arc(20, 40, 60, 80, start=180, extent=180, outline="white", width=2, style=tk.ARC)

        self.canvas_wifi.delete("all")
        
        # 🌟 嚴格判定：必須是 Python 連上 MQTT，且在 15 秒內有收到 ESP32 的心跳/資料，才算真正滿格
        esp32_is_alive = (time.time() - self.last_msg_time < 15.0) and (self.last_msg_time > 0)
        
        if self.mqtt_connected and esp32_is_alive:
            # 雙向連線正常：顯示滿格綠色
            c_dot = c_in = c_out = "#00FF00"
        else:
            # 只要有一方斷線 (伺服器斷線、或 ESP32 斷電/失去回應)：顯示搜尋中的動畫
            p = (self.wifi_tick // 15) % 4
            c_dot = "#00FF00" if p >= 0 and p != 3 else "#444444"
            c_in  = "#00FF00" if p >= 1 and p != 3 else "#444444"
            c_out = "#00FF00" if p >= 2 and p != 3 else "#444444"
            
        self.canvas_wifi.create_oval(22, 31, 28, 37, fill=c_dot, outline=""); self.canvas_wifi.create_arc(15, 23, 35, 43, start=45, extent=90, outline=c_in, width=2, style=tk.ARC); self.canvas_wifi.create_arc(7, 13, 43, 49, start=45, extent=90, outline=c_out, width=2, style=tk.ARC)

        self.root.after(30, self.animate_icons)

if __name__ == "__main__":
    root = tk.Tk()
    app = DashboardApp(root)
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    root.mainloop()