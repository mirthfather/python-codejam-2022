#!/usr/bin/env python3
import asyncio
from datetime import datetime as dt

# import pygame
import websockets
import json

history = []


async def game_server(sock):
    """Main gameserver message handler"""
    print(f'Connection: {sock}')
    async for msg in sock:
        tr = dt.now()
        history.append({
            "time_recv": tr,
            "message": msg})
        ret = []
        while len(history) > 0 and (tr - history[0]["time_recv"]).seconds >= 1:
            ret.append(history[0]["message"])
            history.pop(0)

        await sock.send(json.dumps(ret))


async def main():
    """Main websocket event loop"""
    async with websockets.serve(game_server, "0.0.0.0", 7890):
        await asyncio.Future()


def run():
    """Run main with asyncio.run"""
    asyncio.run(main())


if __name__ == "__main__":
    run()
