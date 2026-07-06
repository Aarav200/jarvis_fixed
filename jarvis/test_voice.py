import asyncio
import edge_tts
import pygame
import time

async def test():
    c = edge_tts.Communicate("Jarvis at your service, sir.", "en-GB-RyanNeural")
    await c.save("test_voice.mp3")
    print("Audio generated successfully!")

asyncio.run(test())

pygame.mixer.init()
pygame.mixer.music.load("test_voice.mp3")
pygame.mixer.music.play()
print("Playing audio...")
time.sleep(4)
print("Done!")
