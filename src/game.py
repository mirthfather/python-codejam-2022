import argparse
import asyncio
import json
import uuid
from typing import Any, Optional

import pygame
import websockets

import gol_abc
import sprites

# width and height of the screen in pixels
# a fullscreen window of variable size would be possible
WIDTH = 640
HEIGHT = 480

# uncomment to implement FPS capping
# MAX_FPS = 60

class Game(gol_abc.SpriteTracker):
    """Object to handle all game-level tasks."""

    def __init__(self, username: str) -> None:
        super().__init__()

        self.running = False

        # make the window for the game
        # self.screen is a Surface
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

        # make a black Surface the size of the screen - used for all_sprites.clear
        # this could be replaced with a background image Surface
        self.background = pygame.Surface((WIDTH, HEIGHT))
        self.background.fill((0, 0, 0))

        self.player = sprites.Player(str(uuid.uuid1()), username)
        self.sprite_map.add(self.player)

        # groups
        self.characters = pygame.sprite.Group(self.player)
        self.gems = pygame.sprite.Group()

        self.clock = pygame.time.Clock()

    @staticmethod
    def check_message(data: dict[str, Any]):
        """
        Checks a message for errors and checks version compatibility.

        :param data: the decoded message data
        :return: None
        """
        if "error" in data:
            print(
                f'Server failed connection with error: {data["error"]}')
            return

        if "version" not in data:
            print('Server did not send version identifier')
            return

        if data["version"] > gol_abc.VERSION:
            print(
                f'Server report advanced version v{data["version"]}. Please update the client')
            return

    async def startup(self, server_addr):
        """Connect to the server and start game loop"""
        # set self.running to False (through exit_game) to end the game
        self.running = True

        async with websockets.connect(f'ws://{server_addr}') as ws:
            # Verify version match with server
            await ws.send(json.dumps({
                "version": gol_abc.VERSION,
                "player_state": self.player.report().to_dict()
            }))

            hello = json.loads(await ws.recv())
            self.check_message(hello)

            if "state" not in hello:
                print(f'Server "{server_addr}" did not send initial game state')
                return

            self.initialize_state(hello["state"])

            game_loop = asyncio.create_task(self.run(ws))

            await game_loop

    async def run(self, ws):
        """Call this method to start the game loop."""
        while self.running:
            await self.loop(ws)
            await asyncio.sleep(0)  # why?

    async def loop(self, ws):
        """Run all aspects of one frame for the client."""
        self.handle_events()

        self.player.update()

        await ws.send(json.dumps({
            "version": gol_abc.VERSION,
            "player_state": self.player.report().to_dict()
        }))

        msg = json.loads(await ws.recv())
        self.check_message(msg)

        if "state" not in msg:
            print('Server did not send next game state')
            self.exit_game()

        self.update_state(msg["state"])
        self.render()

        if "winner" in msg:
            winner = self.sprite_map[msg["winner"]]
            if not isinstance(winner, sprites.Character):
                raise ValueError("bad winner!")

            print("You" if winner is self.player else winner.username,
                  f"won with a score of {winner.score}!")

        # uncomment to implement FPS capping
        # self.clock.tick(MAX_FPS)

    def handle_events(self):
        """Run pygame.event.pump() and close upon window close."""
        # listen for new keyboard and mouse events
        pygame.event.pump()

        # quit if the OS asks the window to close
        if pygame.QUIT in [e.type for e in pygame.event.get()]:
            self.exit_game()

    def initialize_state(self, state_json: str):
        """Initialize game state from server"""
        state: sprites.SpriteDataGroup = sprites.SpriteDataGroup.from_json(state_json)
        for sprite_data in state.data:
            if sprite_data.score is None:
                # gem data
                gem = sprites.Gem.from_spritedata(self, sprite_data)
                self.gems.add(gem)
                self.sprite_map.add(gem)
            elif sprite_data.owner_id is None and sprite_data.score is not None:
                # character data
                if sprite_data.sprite_id == self.player.sprite_id:
                    self.player.update_spritedata(sprite_data)
                    self.ghost_player = sprites.GhostPlayer.from_spritedata(sprite_data)
                else:
                    player = Character.from_spritedata(sprite_data)
                    self.characters.add(player)
                    self.sprite_map.add(player)
            else:
                raise ValueError("invalid sprite data")

        self.all_sprites = pygame.sprite.RenderUpdates(*self.characters.sprites(),
                                                       *self.gems.sprites())

    def update_state(self, state_json: str):
        """Update game state from server"""
        if not state_json:
            # no state; probably in the first second of the game
            return
        state: sprites.SpriteDataGroup = sprites.SpriteDataGroup.from_json(state_json)
        for sprite_data in state.data:
            if sprite_data.score is None:
                # gem data
                self.sprite_map[sprite_data.sprite_id].update_spritedata(sprite_data)
            elif sprite_data.owner_id is None and sprite_data.score is not None:
                # character data
                if sprite_data.sprite_id == self.player.sprite_id:
                    self.ghost_player.update_spritedata(sprite_data)
                else:
                    self.sprite_map[sprite_data.sprite_id].update_spritedata(sprite_data)
            else:
                print(f"{sprite_data.score=}")
                print(f"{sprite_data.owner_id=}")
                raise ValueError("invalid sprite data")

    def render(self):
        """Perform everything that needs to be done to draw all changes."""
        # clear dirty areas left by sprites' previous locations
        # comment out this line to see why it's necessary :P
        self.all_sprites.clear(self.screen, self.background)
        # draw everything
        dirty = self.all_sprites.draw(self.screen)
        # update only the areas that have changed
        pygame.display.update(dirty)

    def exit_game(self):
        """Stop the game after the current loop finishes."""
        self.running = False


def main():
    """Function that runs the game."""
    # parse CLI arguments
    ap = argparse.ArgumentParser(description='Game of Lag')
    ap.add_argument("username", type=str)
    ap.add_argument('-s', '--server', default='localhost')
    ap.add_argument('-p', '--port', type=int, default=7890)
    args = ap.parse_args()

    # initialize all pygame modules
    pygame.init()

    game = Game(args.username)
    asyncio.run(game.startup(f'{args.server}:{args.port}'))


if __name__ == "__main__":
    main()
