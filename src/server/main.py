#!/usr/bin/env python3
import asyncio
import json

# import pygame
import websockets

from ..game.game import Game

history = []

VERSION = 1.0


async def game_server(ws):
    """Main gameserver message handler"""
    game = Game(server=True)

    client_addr = ws.remote_address[0]
    hello = json.loads(await ws.recv())
    if 'version' not in hello:
        print(f'Connection {client_addr} did not send version information. Disconnecting')
        return

    if hello['version'] < VERSION:
        print(f'Connection {client_addr} using version v{hello["version"]}. Disconnecting')
        return

    print(f'Connection established: {client_addr}')

    await ws.send(json.dumps({
        "version": VERSION,
        "state": game.report_state()
    }))

    async for msg in ws:
        # tr = dt.now()
        # history.append({
        #     "time_recv": tr,
        #     "message": msg})
        # ret = []
        # while len(history) > 0 and (tr - history[0]["time_recv"]).seconds >= 1:
        #     ret.append(history[0]["message"])
        #     history.pop(0)
        history.append(msg)
        if len(history) >= 60:
            ret = history.pop(0)
            await game.loop_server(ws, ret)
        else:
            # send empty state because we have not had enough frames yet
            await ws.send(json.dumps({
                "version": VERSION,
                "state": ""
            }))

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
