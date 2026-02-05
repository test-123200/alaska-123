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
        self.interval = 300  # 5 minutes

    async def start(self):
        while True:
            await self.capture_and_upload()
            await asyncio.sleep(self.interval)

    async def capture_and_upload(self):
        with mss.mss() as sct:
            # Capture the primary monitor
            monitor = sct.monitors[1]
            output = f"screenshot_{int(time.time())}.png"
            
            try:
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=output)
                
                # Upload to Supabase Storage
                with open(output, 'rb') as f:
                    file_path = f"{self.employee_id}/{output}"
                    self.supabase.storage.from_("screenshots").upload(
                        file=f,
                        path=file_path,
                        file_options={"content-type": "image/png"}
                    )
                
                # Get Public URL (or signed URL if private, but we need to store reliable access)
                # For private buckets we might store the path and let the frontend sign it, 
                # or sign it here with a long expiration.
                # Assuming simple pattern: store the path, frontend handles display.
                
                # Insert record into database
                self.supabase.table("screenshots").insert({
                    "employee_id": self.employee_id,
                    "storage_path": file_path,
                    "url": file_path # Storing path as URL for now, let frontend resolve
                }).execute()
                
                print(f"Screenshot uploaded: {output}")

            except Exception as e:
                print(f"Check if bucket 'screenshots' exists. Error uploading screenshot: {e}")
            finally:
                if os.path.exists(output):
                    os.remove(output)
