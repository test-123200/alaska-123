import asyncio
import time
import os
import mss
import mss.tools
from supabase import Client

log_file = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'agent.log')
def log(msg):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[Screenshot] {msg}\n")
    except:
        pass

class ScreenshotService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.default_interval = 300 
        self.cache_dir = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'screenshots')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.max_cache_files = 10
        self.enabled = False
        self.current_interval = self.default_interval

    async def start(self):
        log("Service started.")
        await self.sync_cache()
        
        while True:
            await self.check_config()
            await self.poll_commands()
            
            if self.enabled:
                await self.capture()
                await asyncio.sleep(self.current_interval)
            else:
                await asyncio.sleep(5)

    async def check_config(self):
        try:
            response = self.supabase.table("employees").select("settings").eq("id", self.employee_id).single().execute()
            if response.data and response.data.get("settings"):
                settings = response.data["settings"]
                self.current_interval = settings.get("screenshot_interval", self.default_interval)
                self.enabled = settings.get("screenshots_enabled", False)
        except Exception as e:
            log(f"Config error: {e}")

    async def poll_commands(self):
        try:
            response = self.supabase.table("commands")\
                .select("*")\
                .eq("employee_id", self.employee_id)\
                .eq("command_type", "TAKE_SCREENSHOT")\
                .eq("status", "PENDING")\
                .execute()
            
            for cmd in response.data:
                log(f"On-demand screenshot requested.")
                await self.capture()
                self.supabase.table("commands").update({"status": "EXECUTED"}).eq("id", cmd["id"]).execute()
        except Exception as e:
            log(f"Poll error: {e}")

    async def capture(self):
        filename = f"screenshot_{int(time.time())}.png"
        cache_path = os.path.join(self.cache_dir, filename)

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=cache_path)
            
            log(f"Captured: {filename}")
            self.prune_cache()

            uploaded = await self.upload_file(cache_path, filename)
            if uploaded:
                log(f"Uploaded: {filename}")
                self.delete_file(cache_path)
            else:
                log(f"Cached: {filename}")

        except Exception as e:
            log(f"Capture error: {e}")

    async def upload_file(self, file_path, filename):
        try:
            with open(file_path, 'rb') as f:
                storage_path = f"{self.employee_id}/{filename}"
                self.supabase.storage.from_("screenshots").upload(
                    file=f, path=storage_path, file_options={"content-type": "image/png", "upsert": "true"}
                )
                
            self.supabase.table("screenshots").insert({
                "employee_id": self.employee_id, 
                "storage_path": storage_path, 
                "url": storage_path
            }).execute()
            return True
        except Exception as e:
            log(f"Upload error: {e}")
            return False

    async def sync_cache(self):
        try:
            files = [os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith('.png')]
            for fpath in files:
                fname = os.path.basename(fpath)
                if await self.upload_file(fpath, fname):
                    log(f"Synced: {fname}")
                    self.delete_file(fpath)
        except Exception as e:
            log(f"Sync error: {e}")

    def prune_cache(self):
        try:
            files = sorted([os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith('.png')], key=os.path.getctime)
            if len(files) > self.max_cache_files:
                for f in files[:len(files) - self.max_cache_files]:
                    self.delete_file(f)
        except:
            pass

    def delete_file(self, path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
