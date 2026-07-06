import subprocess
import sys

script = """
import asyncio
import edge_tts

async def run():
    c = edge_tts.Communicate("hello sir", "en-GB-RyanNeural")
    await c.save("edge_test.mp3")
    print("SUCCESS")

asyncio.run(run())
"""

r = subprocess.run(
    [sys.executable, "-c", script],
    capture_output=True,
    timeout=15
)
print("Return code:", r.returncode)
print("Stdout:", r.stdout.decode())
print("Stderr:", r.stderr.decode())

if r.returncode == 0:
    print("\nEdge TTS subprocess works! Playing audio...")
    import pygame
    import time
    pygame.mixer.init()
    pygame.mixer.music.load("edge_test.mp3")
    pygame.mixer.music.play()
    time.sleep(4)
else:
    print("\nEdge TTS subprocess FAILED - this is why voice is robotic")
