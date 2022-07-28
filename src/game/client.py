import asyncio
import websockets

async def send_and_recieve(keypress):
    async with websockets.connect("ws://localhost:8765") as websocket:
        await websocket.send(keypress)
        async for message in websocket:
            print(message)

async def main(queue):
    tasks = []
    for key in queue:
        tasks.append(asyncio.create_task(send_and_recieve(key)))
    await asyncio.gather(*tasks, return_exceptions=True)

q = ["Left", "Right", "Up", "Down", "Left", "Right", "Up", "Down", "Left", "Right", "Up", "Down"]
asyncio.run(main(q))