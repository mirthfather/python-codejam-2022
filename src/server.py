#!/usr/bin/env python3
import asyncio
import json
import random
import uuid

import pygame
import websockets

import gol_abc
import sprites

history = []

# For now, these are copied from game.py, but in the future, there needs to be
# some way to communicate width and height---perhaps just as arguments to
# Sprite constructors.
#
# Right now, the only way I see to handle both fullscreen and players with
# different screen sizes is to make the "map" bigger than anyone's screen and
# have players scroll through it
WIDTH = 640
HEIGHT = 480


class Server(gol_abc.SpriteTracker):

    # how many gems to start the game with
    GEM_NUMBER = 10

    def __init__(self):
        super().__init__()

        self.gems = self.create_gems()
        # in the future, add other human players to this group
        self.characters = pygame.sprite.Group()

    async def loop(self, ws, client_update: str):
        """Run all aspects of one frame for the server."""
        # call update methods of each sprite in the group
        self.characters.update()
        for gem in self.gems:
            # Passing collision data through update instead of using a
            # groupcollide later with another method makes it easier for Gems to
            # notice when a character is no longer colliding with them.
            gem.update(pygame.sprite.spritecollide(gem, self.characters, False), gol_abc.timestamp())

        #print(f"{client_update=}")
        data = sprites.SpriteData.from_dict(json.loads(client_update)["player_state"])

        self.sprite_map[data.sprite_id].update_spritedata(data)

        # if no gem sprites remain, quit
        if not self.gems:
            winner = sorted(self.characters.sprites(), key=lambda c: c.score, reverse=True)[0]
            if not isinstance(winner, Character):
                raise ValueError("bad winner!")
            await ws.send(json.dumps(
                {
                    "version": gol_abc.VERSION,
                    "state": self.report_state(),
                    "winner": winner.sprite_id,
                }
            ))
            self.exit_game()

        await ws.send(json.dumps(
            {
                "version": gol_abc.VERSION,
                "state": self.report_state()
            }
        ))

    def report_state(self) -> str:
        """Report game state to be sent to the client"""
        all_sprites = [sprite.report() for sprite in self.sprite_map.sprites()]
        return sprites.SpriteDataGroup(all_sprites).to_json()

    def create_gems(self):
        """Return a Group of Game.GEM_NUMBER gems."""
        gems = pygame.sprite.Group()
        for _ in range(Server.GEM_NUMBER):
            gem = sprites.Gem(self, str(uuid.uuid1()))
            gems.add(gem)
            self.sprite_map.add(gem)
        return gems

    def add_player(self, data: sprites.SpriteData) -> None:
        """Add a player based on sprite data."""
        if data.sprite_id in self.sprite_map.ids():
            raise ValueError("a player with that ID is already in the game")
        self.sprite_map.add(sprites.Character(
            data.sprite_id,
            data.username,
            (
                random.uniform(sprites.Character.WIDTH/2, WIDTH-(sprites.Character.WIDTH/2)),
                random.uniform(sprites.Character.HEIGHT/2, HEIGHT-(sprites.Character.HEIGHT/2))
            )
        ))
        self.sprite_map[data.sprite_id].update_spritedata(data)

async def game_server(ws):
    """Main gameserver message handler"""
    server = Server()

    client_addr = ws.remote_address[0]
    hello = json.loads(await ws.recv())
    if 'version' not in hello:
        print(f'Connection {client_addr} did not send version information. Disconnecting')
        return

    if hello['version'] < gol_abc.VERSION:
        print(f'Connection {client_addr} using version v{hello["version"]}. Disconnecting')
        return

    if "player_state" not in hello:
        print(f"Connection {client_addr} did not send player state. Disconnecting")
        return

    print(f'Connection established: {client_addr}')

    data = sprites.SpriteData.from_dict(hello["player_state"])
    # make a player according to the player state sent from the client
    server.add_player(data)

    await ws.send(json.dumps({
        "version": gol_abc.VERSION,
        "state": server.report_state()
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
        # throw a number here until I find out what this is doing
        #if len(history) >= gol_abc.FPS:
        if len(history) >= 60:
            ret = history.pop(0)
            await server.loop(ws, ret)
        else:
            # send empty state because we have not had enough frames yet
            await ws.send(json.dumps({
                "version": gol_abc.VERSION,
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
