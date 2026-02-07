import asyncio
import time
import os
import shutil
import mss
import mss.tools
from typing import List
from supabase import Client

class ScreenshotService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.default_interval = 300 
        self.cache_dir = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'screenshots')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.max_cache_files = 10
        self.enabled = False 

    async def start(self):
        print("ScreenshotService started.")
        await self.sync_cache()
        
        while True:
            await self.check_config()
            if self.enabled:
                await self.capture()
                await asyncio.sleep(self.current_interval)
            else:
                await asyncio.sleep(10)

    async def check_config(self):
        try:
            response = self.supabase.table("employees").select("settings").eq("id", self.employee_id).single().execute()
            if response.data and response.data.get("settings"):
                settings = response.data["settings"]
                self.current_interval = settings.get("screenshot_interval", self.default_interval)
                self.enabled = settings.get("screenshots_enabled", False) # Default to false for "On Demand" style
        except:
            pass 

    async def capture(self):
        filename = f"screenshot_{int(time.time())}.png"
        cache_path = os.path.join(self.cache_dir, filename)

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=cache_path)
            
            self.prune_cache()

            uploaded = await self.upload_file(cache_path, filename)
            if uploaded:
                print(f"Screenshot uploaded: {filename}")
                self.delete_file(cache_path)
            else:
                print(f"Offline. Screenshot cached: {filename}")
                await self.sync_cache()

        except Exception as e:
            print(f"Capture error: {e}")

    async def upload_file(self, file_path, filename):
        try:
            with open(file_path, 'rb') as f:
                storage_path = f"{self.employee_id}/{filename}"
                self.supabase.storage.from_("screenshots").upload(
                    file=f, path=storage_path, file_options={"content-type": "image/png"}
                )
            self.supabase.table("screenshots").insert({
                "employee_id": self.employee_id, 
                "storage_path": storage_path, 
                "url": storage_path
            }).execute()
            return True
        except Exception:
            return False

    async def sync_cache(self):
        files = [os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith('.png')]
        for fpath in files:
            fname = os.path.basename(fpath)
            if await self.upload_file(fpath, fname):
                print(f"Synced cached screenshot: {fname}")
                self.delete_file(fpath)

    def prune_cache(self):
        files = sorted(
            [os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith('.png')],
            key=os.path.getctime
        )
        if len(files) > self.max_cache_files:
            to_remove = files[:len(files) - self.max_cache_files]
            for f in to_remove:
                self.delete_file(f)

    def delete_file(self, path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
