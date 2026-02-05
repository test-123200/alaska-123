import asyncio
import json
import pyautogui
from supabase import Client

class ControlService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id

    async def start(self):
        print("ControlService started. Listening for commands...")
        # In a real scenario, we'd use Supabase Realtime 'INSERT' events on the 'commands' table.
        # However, the Python client's realtime subscriptions can be tricky in some envs.
        # Alternatively, we can poll or use the realtime-py library if installed.
        # For this implementation, I will simulate polling for reliability in this prototype, 
        # but in production, Realtime is preferred.
        
        # Realtime implementation:
        # channel = self.supabase.channel('commands')
        # channel.on('postgres_changes', event='INSERT', schema='public', table='commands', filter=f"employee_id=eq.{self.employee_id}", callback=self.handle_command).subscribe()
        
        # Polling fallback for simplicity and stability in this agent script
        while True:
            await self.poll_commands()
            await asyncio.sleep(2)

    async def poll_commands(self):
        try:
            response = self.supabase.table("commands")\
                .select("*")\
                .eq("employee_id", self.employee_id)\
                .eq("status", "PENDING")\
                .execute()
            
            commands = response.data
            for cmd in commands:
                await self.execute_command(cmd)
        except Exception as e:
            print(f"Error polling commands: {e}")

    async def execute_command(self, cmd):
        # cmd: {id, command_type, payload}
        cmd_type = cmd.get("command_type")
        payload = cmd.get("payload", {})
        
        print(f"Executing command: {cmd_type} {payload}")
        
        try:
            if cmd_type == "CLICK":
                x = payload.get("x")
                y = payload.get("y")
                if x is not None and y is not None:
                    # PyAutoGUI failsafe is enabled by default (moving mouse to corner throws exception)
                    # We might want to disable it or handle it.
                    pyautogui.click(x=x, y=y)
            
            elif cmd_type == "TYPE":
                text = payload.get("text")
                if text:
                    pyautogui.write(text)

            elif cmd_type == "SCROLL":
                amount = payload.get("amount")
                if amount:
                    pyautogui.scroll(amount)

            # Mark as executed
            self.supabase.table("commands").update({"status": "EXECUTED"}).eq("id", cmd["id"]).execute()
        
        except Exception as e:
            print(f"Error executing command {cmd['id']}: {e}")
            self.supabase.table("commands").update({"status": "ERROR"}).eq("id", cmd["id"]).execute()
