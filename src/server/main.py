#!/usr/bin/env python3
import asyncio

import websockets


async def game_server(sock):
    """Main gameserver message handler"""
    async for msg in sock:
        await sock.send("Not implemented")


async def main():
    """Main websocket event loop"""
    async with websockets.serve(game_server, "0.0.0.0", 7890):
        await asyncio.Future()


def run():
    """Run main with asyncio.run"""
    asyncio.run(main())


if __name__ == "__main__":
    run()
