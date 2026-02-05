import asyncio
import time
import os
import mss
import mss.tools
from supabase import Client

class ScreenshotService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.default_interval = 300 # 5 minutes

    async def start(self):
        while True:
            # 1. Fetch current settings (Dynamic Loop)
            interval = await self.get_interval()
            
            await self.capture_and_upload()
            
            # Wait dynamically based on current setting
            await asyncio.sleep(interval)

    async def get_interval(self):
        try:
            response = self.supabase.table("employees").select("settings").eq("id", self.employee_id).single().execute()
            if response.data and response.data.get("settings"):
                return response.data["settings"].get("screenshot_interval", self.default_interval)
        except:
            pass
        return self.default_interval

    async def capture_and_upload(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            output = f"screenshot_{int(time.time())}.png"
            
            try:
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=output)
                
                with open(output, 'rb') as f:
                    file_path = f"{self.employee_id}/{output}"
                    self.supabase.storage.from_("screenshots").upload(
                        file=f,
                        path=file_path,
                        file_options={"content-type": "image/png"}
                    )
                
                self.supabase.table("screenshots").insert({
                    "employee_id": self.employee_id,
                    "storage_path": file_path,
                    "url": file_path
                }).execute()
                
                print(f"Screenshot uploaded: {output}")

            except Exception as e:
                print(f"Error uploading screenshot: {e}")
            finally:
                if os.path.exists(output):
                    os.remove(output)
