import asyncio
import json
import logging
import time
import cv2
import mss
import numpy as np
import pyautogui
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame
from supabase import Client

# Disable pyautogui fail-safe
pyautogui.FAILSAFE = False

class ScreenVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        # Capture screen
        sct_img = self.sct.grab(self.monitor)
        frame = VideoFrame.from_ndarray(np.array(sct_img), format="bgra")
        frame.pts = pts
        frame.time_base = time_base
        return frame

class CameraVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        ret, img = self.cap.read()
        if not ret:
            # Create black frame if cam fails
            img = np.zeros((480, 640, 3), dtype=np.uint8)
        
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame

class WebRTCService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.pc = None
        self.screen_track = None
        self.cam_track = None

    async def start(self):
        print("WebRTC Service started. Listening for signaling...")
        
        # Subscribe to signaling channel
        self.channel = self.supabase.channel(f"signaling-{self.employee_id}")
        self.channel.on("broadcast", {"event": "OFFER"}, self.handle_offer).subscribe()
        self.channel.on("broadcast", {"event": "ICE_CANDIDATE"}, self.handle_ice).subscribe()
        
        # Subscribe to Control Events (Mouse/Keyboard)
        self.control_channel = self.supabase.channel(f"control-{self.employee_id}")
        self.control_channel.on("broadcast", {"event": "MOUSE_MOVE"}, self.handle_mouse_move).subscribe()
        self.control_channel.on("broadcast", {"event": "MOUSE_CLICK"}, self.handle_mouse_click).subscribe()
        self.control_channel.on("broadcast", {"event": "KEY_PRESS"}, self.handle_key_press).subscribe()

        while True:
            await asyncio.sleep(1)

    async def handle_offer(self, payload):
        print("Received OFFER")
        offer_sdp = payload["payload"]["sdp"]
        offer = RTCSessionDescription(sdp=offer_sdp, type="offer")

        if self.pc:
            await self.pc.close()
        
        self.pc = RTCPeerConnection()
        
        # Add Tracks
        self.screen_track = ScreenVideoTrack()
        self.cam_track = CameraVideoTrack()
        self.pc.addTrack(self.screen_track)
        self.pc.addTrack(self.cam_track)

        @self.pc.on("iceconnectionstatechange")
        async def on_icestate_change():
            print(f"ICE Connection State: {self.pc.iceConnectionState}")

        await self.pc.setRemoteDescription(offer)
        
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        # Send Answer back
        await self.channel.send({
            "type": "broadcast",
            "event": "ANSWER",
            "payload": {"sdp": self.pc.localDescription.sdp, "type": self.pc.localDescription.type}
        })
        print("Sent ANSWER")

    async def handle_ice(self, payload):
        candidate = payload["payload"]
        # AIORTC handles ICE internally mostly, but for full trickle ICE 
        # we might need to addCandidate. However, simple Offer/Answer usually works 
        # if STUN is configured. For now, we rely on the Offer/Answer gathering.
        pass

    async def handle_mouse_move(self, payload):
        try:
            x_norm = payload["payload"]["x"]
            y_norm = payload["payload"]["y"]
            width, height = pyautogui.size()
            pyautogui.moveTo(x_norm * width, y_norm * height)
        except Exception as e:
            print(f"Mouse Move Error: {e}")

    async def handle_mouse_click(self, payload):
        try:
            x_norm = payload["payload"]["x"]
            y_norm = payload["payload"]["y"]
            btn = payload["payload"].get("button", "left")
            width, height = pyautogui.size()
            pyautogui.click(x_norm * width, y_norm * height, button=btn)
        except Exception as e:
            print(f"Click Error: {e}")

    async def handle_key_press(self, payload):
        try:
            key = payload["payload"]["key"]
            # Map special keys if needed or use press/write
            if len(key) > 1:
                pyautogui.press(key)
            else:
                pyautogui.write(key)
        except Exception as e:
            print(f"Key Error: {e}")
