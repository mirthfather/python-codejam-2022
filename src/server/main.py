#!/usr/bin/env python3
import asyncio
import json
from datetime import datetime as dt

# import pygame
import websockets

history = []


async def game_server(ws):
    """Main gameserver message handler"""
    client_addr = ws.remote_address[0]
    hello = json.loads(await ws.recv())
    if 'version' not in hello:
        print(f'Connection {client_addr} did not send version information. Disconnecting')
        return

    if hello['version'] < 1.0:
        print(f'Connection {client_addr} using version v{hello["version"]}. Disconnecting')
        return

    print(f'Connection established: {client_addr}')

    await ws.send(json.dumps({
        "version": 1.0
    }))

    async for msg in ws:
        tr = dt.now()
        history.append({
            "time_recv": tr,
            "message": msg})
        ret = []
        while len(history) > 0 and (tr - history[0]["time_recv"]).seconds >= 1:
            ret.append(history[0]["message"])
            history.pop(0)

        await ws.send(json.dumps(ret))

    print(f'Connection terminated: {client_addr}')


async def main():
    """Main websocket event loop"""
    async with websockets.serve(game_server, "0.0.0.0", 7890):
        await asyncio.Future()


def run():
    """Run main with asyncio.run"""
    asyncio.run(main())


if __name__ == "__main__":
    run()
