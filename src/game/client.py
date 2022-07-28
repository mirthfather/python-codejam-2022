"""
Each frame send a single keypress to the server.
Each frame retrieve multiple keypresses from the server (one per player).
Each frame process the keypresses from the server. 
"""

import asyncio
import websockets

async def send_and_recieve(keypress):
    async with websockets.connect("ws://localhost:8765") as websocket:
        await websocket.send(keypress)
        async for key in websocket:
            await update_game_from_server_keypress(key)

async def update_game_from_server_keypress(keypress):
    print(f'handle server response {keypress}')

if __name__ == "__main__":
    asyncio.run(send_and_recieve("Left"))


