import asyncio
import time
import os
import tempfile
import mss
import mss.tools
from supabase import Client

class ScreenshotService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.default_interval = 300 

    async def start(self):
        print("ScreenshotService started.")
        while True:
            interval = await self.get_interval()
            await self.capture_and_upload()
            await asyncio.sleep(interval)

    async def get_interval(self):
        try:
            response = self.supabase.table("employees").select("settings").eq("id", self.employee_id).single().execute()
            if response.data and response.data.get("settings"):
                return response.data["settings"].get("screenshot_interval", self.default_interval)
        except Exception as e:
            print(f"Error fetching interval: {e}")
        return self.default_interval

    async def capture_and_upload(self):
        # Use System Temp Directory
        temp_dir = tempfile.gettempdir()
        filename = f"screenshot_{int(time.time())}.png"
        output_path = os.path.join(temp_dir, filename)

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=output_path)
            
            with open(output_path, 'rb') as f:
                storage_path = f"{self.employee_id}/{filename}"
                print(f"Uploading screenshot to: {storage_path}")
                
                res = self.supabase.storage.from_("screenshots").upload(
                    file=f,
                    path=storage_path,
                    file_options={"content-type": "image/png"}
                )
                if hasattr(res, 'error') and res.error:
                     print(f"Upload API Error: {res.error}")
                     return

            self.supabase.table("screenshots").insert({
                "employee_id": self.employee_id,
                "storage_path": storage_path,
                "url": storage_path
            }).execute()
            
            print(f"Screenshot uploaded successfully: {filename}")

        except Exception as e:
            print(f"CRITICAL: Screenshot upload failed: {e}")
        finally:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                   pass
