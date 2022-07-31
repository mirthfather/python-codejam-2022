import argparse
import asyncio
import json
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple, Union

import numpy as np
import pygame
import websockets
from dataclasses_json import dataclass_json

# width and height of the screen in pixels
# a fullscreen window of variable size would be possible
WIDTH = 640
HEIGHT = 480

# target frames per second
FPS = 60

# client version
VERSION = 1.0


@dataclass_json
@dataclass
class SpriteData:
    """Class to represent the current state data of a character or gem."""

    # common attributes
    sprite_id: str
    pos: tuple[float, float]
    # Character attributes
    username: Optional[str] = field(default=None)
    velocity: Optional[tuple[float, float]] = field(default=None)
    score: Optional[int] = field(default=None)
    # Gem attributes
    until_dead: Optional[float] = field(default=None)
    prev_until_dead: Optional[float] = field(default=None)
    dead_timer: Optional[float] = field(default=None)
    owner_id: Optional[str] = field(default=None)
    alive: Optional[bool] = field(default=None)


@dataclass_json
@dataclass
class SpriteDataGroup:
    """Json-(un)serializable wrapper for a list of SpriteData objects"""

    data: list[SpriteData]


class AbstractSprite(pygame.sprite.Sprite):
    """An abstract class for shared code between Gem and Character."""

    def __init__(
        self,
        game: 'Game',
        sprite_id: str,
        width: int,
        height: int,
        color: pygame.Color
    ):
        super().__init__()
        self.game: Game = game
        self.sprite_id: str = sprite_id

        # image is a specially recognized Sprite attribute
        # for now, it is a solid color, but pygame.image.load returns an image as a Surface
        self.image = pygame.Surface((width, height))
        self.image.fill(color)

        # rect is also a specially recognized Sprite attribute
        self.rect: pygame.Rect = self.image.get_rect()

    def report(self) -> SpriteData:
        """
        Report the current state of this sprite as SpriteData.

        :return: the current state
        """
        pass

    @classmethod
    def from_spritedata(cls, game: 'Game', data: SpriteData) -> 'AbstractSprite':
        """
        Instantiate an object of this class for a given game using SpriteData.

        :param game: the current game
        :param data: the state to use
        :return: the new object
        """
        pass

    def update_spritedata(self, data: SpriteData) -> None:
        """
        Update the state of a sprite using SpriteData.

        :param data: the state to use
        :return: None
        """
        pass

    def check_sprite_id(self, sprite_id: str) -> None:
        """
        Validate a sprite ID against this object's sprite ID.

        Raise ValueError if they do not match.

        :param sprite_id: the ID to check
        :return: None
        """
        if sprite_id != self.sprite_id:
            raise ValueError('mismatched sprite ID')


class Character(AbstractSprite):
    """A character controlled by a player."""

    # pixels per second per second, converted to pixels per frame per frame
    THRUST = 50 * FPS**(-2)

    WIDTH = 25
    HEIGHT = 25

    COLOR = (255, 0, 0)

    def __init__(self, game: 'Game', sprite_id: str, username: str):
        super().__init__(
            game,
            sprite_id,
            self.WIDTH,
            self.HEIGHT,
            pygame.Color(*self.COLOR)
        )

        self.username = username

        # track position independently of the rect, enabling floating-point precision
        # place the character in a random starting spot (maybe assigned by the server in the future?)
        self.pos = np.array((random.uniform(Character.WIDTH/2, WIDTH-(Character.WIDTH/2)),
                             random.uniform(Character.HEIGHT/2, HEIGHT-(Character.HEIGHT/2))))

        # pixels per second
        self.velocity = np.zeros(2)

        self.score = 0

    def move(self, thrust: np.ndarray):
        """Correct the magnitude of the thrust and move the character accordingly."""
        # normalize the direction so that moving diagonally does not move faster
        # this is done by dividing the thrust by its magnitude
        # the 'or 1' causes division by 1 if the magnitude is 0 to avoid zero division errors
        #
        # Note: if it is possible to standardize thrusts on a scale of 0 to 1,
        #       this could be optimized by dividing by sqrt(2) or not at all
        thrust /= np.sqrt((thrust**2).sum()) or 1
        # The previous line normalized the thrust's magnitude to 1. Now we
        # change that magnitude to Character.THRUST simply by multiplication.
        thrust *= Character.THRUST

        self.velocity += thrust
        self.pos += self.velocity

        # prevent the character from going off the screen
        #
        # Keep in mind that it is not the center that must not go off screen,
        # but rather any part of the character, hence the multiple appearances
        # of WIDTH / 2 and HEIGHT / 2.
        pos_before_correction = self.pos.copy()
        self.pos = np.minimum((
            WIDTH-(Character.WIDTH/2), HEIGHT-(Character.HEIGHT/2)),
            np.maximum((Character.WIDTH/2, Character.HEIGHT/2), self.pos)
        )
        # set velocity to zero after running into the edge of the screen
        #
        # The != generates a new array of booleans, hence the .any
        if (pos_before_correction != self.pos).any():
            self.velocity = np.zeros(2)

        # changing the rect's center automatically changes the sprite's position
        self.rect.center = self.pos

    def increment_score(self):
        """Increase this Character's score by 1."""
        self.score += 1
        print(self, "scored!")

    def report(self) -> SpriteData:
        """
        Report the current state of this sprite as SpriteData.

        :return: the current state
        """
        return SpriteData(
            # general attributes
            sprite_id=self.sprite_id,
            pos=tuple(self.pos),
            # Character attributes
            username=self.username,
            velocity=tuple(self.velocity),
            score=self.score,
        )

    @classmethod
    def from_spritedata(cls, game: 'Game', data: SpriteData) -> 'Character':
        """
        Instantiate an object of this class for a given game using SpriteData.

        :param game: the current game
        :param data: the state to use
        :return: the new object
        """
        obj = cls(game, data.sprite_id, data.username)
        obj.update_spritedata(data)
        return obj

    def update_spritedata(self, data: SpriteData) -> None:
        """
        Update the state of a sprite using SpriteData.

        :param data: the state to use
        :return: None
        """
        self.check_sprite_id(data.sprite_id)

        self.pos = data.pos
        self.velocity = data.velocity
        self.score = data.score


class OtherPlayer(Character):
    """A Character controlled by updates from the server."""

    COLOR = (255, 0, 255)

    def __init__(self, game: 'Game', sprite_id: str, username: str):
        super().__init__(game, sprite_id, username)

    def update(self,
               pos: Tuple[float, float],
               velocity: Tuple[float, float],
               ):
        """This method is called every frame."""
        self.rect.center = np.array(pos)
        self.velocity = np.array(velocity)


class GhostPlayer(OtherPlayer):
    """The ghost of the current player as reported by the server."""

    COLOR = (0, 255, 255, 127)


class Player(Character):
    """A Character that can be controlled locally by the keyboard."""

    COLOR = (0, 255, 255)

    def __init__(self, game: 'Game', sprite_id: str, username: str):
        super().__init__(game, sprite_id, username)

    def update(self):
        """This method is called every frame."""
        # acceleration vector
        # This only provides direction; magnitude is calculated in Character.move
        thrust = np.zeros(2)

        if pygame.key.get_pressed()[pygame.K_LEFT]:
            thrust[0] = -1
        if pygame.key.get_pressed()[pygame.K_RIGHT]:
            thrust[0] = 1
        # in pygame coordinates, up is negative and down is positive
        if pygame.key.get_pressed()[pygame.K_UP]:
            thrust[1] = -1
        if pygame.key.get_pressed()[pygame.K_DOWN]:
            thrust[1] = 1

        super().move(thrust)


class Gem(AbstractSprite):
    """A gem for a character to pick up."""

    WIDTH = 10
    HEIGHT = 10

    COLOR = (0, 255, 0)
    DEAD_COLOR = (255, 0, 0)

    # how long the Sprite should flash after being picked up
    # seconds, converted to frames
    DEAD_TIME = 0.5 * FPS
    # how long each flash when dead is in seconds, converted to frames
    DEAD_FLASH_TIME = 0.15 * FPS

    # how long it takes a Character to pick up a Gem
    # seconds, converted to frames
    PICKUP_TIME = 0.5 * FPS

    def __init__(self,
                 game: 'Game',
                 sprite_id: str,
                 ):
        super().__init__(game, sprite_id, Gem.WIDTH, Gem.HEIGHT, pygame.Color(Gem.COLOR))

        # place the Gem in a random spot on the screen
        self.rect.center = (random.randint(Gem.WIDTH//2, WIDTH-(Gem.WIDTH//2)),
                            random.randint(Gem.HEIGHT//2, HEIGHT-(Gem.HEIGHT//2)))

        # number of frames until gem is picked up by a character
        self.until_dead = Gem.PICKUP_TIME
        # used to track if the owner has left
        self.prev_until_dead = self.until_dead
        self.dead_timer = Gem.DEAD_TIME

        self.owner: Union[Character, None] = None

        self.alive = True

    def update(self) -> None:
        """Called every frame."""
        # if this gem has already been picked up
        if self.until_dead <= 0:
            self.dead_timer -= 1
            if self.dead_timer <= 0:
                # built-in Sprite method that removes this Sprite from all groups
                self.kill()

            # toggle transparency/opaqueness to create a flashing effect
            if self.dead_timer % Gem.DEAD_FLASH_TIME == 0:
                # set alpha to 255 if it's currently 0 and 0 if it's currently 255
                self.image.set_alpha(255 - self.image.get_alpha())

        # if this gem has not yet been picked up
        else:
            # change transparency based on until_dead value
            self.image.set_alpha((self.until_dead/Gem.PICKUP_TIME) * 255)

            # reset the counter if the owner has left
            # this is triggered by noticing that until_dead has not been decremented
            if self.prev_until_dead == self.until_dead:
                self.owner = None
                self.until_dead = Gem.PICKUP_TIME

            self.prev_until_dead = self.until_dead

    def on_collide(self, character: Character) -> None:
        """
        Call each frame when the gem is colliding with at least one Character.

        Automatically increments the correct score if necessary.
        """
        # if this gem is not currently being picked up
        if self.until_dead == Gem.PICKUP_TIME:
            # assign a new owner
            self.owner = character
            self.until_dead -= 1
        # if this gem is already being picked up
        else:
            self.until_dead -= 1
            if self.until_dead <= 0:
                self.die()
                self.owner.increment_score()

    def die(self):
        """Prepare for the "flashing after death" state."""
        # change the gem's color
        self.image.fill(pygame.Color(Gem.DEAD_COLOR))
        # make the gem opaque
        self.image.set_alpha(255)

        self.alive = False

    def report(self) -> SpriteData:
        """
        Report the current state of this sprite as SpriteData.

        :return: the current state
        """
        return SpriteData(
            # general attributes
            sprite_id=self.sprite_id,
            pos=self.rect.center,
            # Gem attributes
            until_dead=self.until_dead,
            prev_until_dead=self.prev_until_dead,
            dead_timer=self.dead_timer,
            owner_id=self.owner.sprite_id,
            alive=self.alive
        )

    @classmethod
    def from_spritedata(cls, game: 'Game', data: SpriteData) -> 'Gem':
        """
        Instantiate an object of this class for a given game using SpriteData.

        :param game: the current game
        :param data: the state to use
        :return: the new object
        """
        obj = cls(game, data.sprite_id)
        obj.update_spritedata(data)
        return obj

    def update_spritedata(self, data: SpriteData) -> None:
        """
        Update the state of a sprite using SpriteData.

        :param data: the state to use
        :return: None
        """
        self.check_sprite_id(data.sprite_id)

        self.rect.center = data.pos
        self.until_dead = data.until_dead
        self.prev_until_dead = data.prev_until_dead
        self.dead_timer = data.dead_timer
        self.owner = self.game.sprite_map[data.owner_id]
        self.alive = data.alive


class Game(object):
    """Object to handle all game-level tasks."""

    # how many gems to start the game with
    GEM_NUMBER = 10

    def __init__(self, server: bool = False, username: Optional[str] = None):
        if not server and username is None:
            raise ValueError("Need a username for client startup")
        self.server = server
        self.running = False

        size = (WIDTH, HEIGHT)
        if not self.server:
            # make the window for the game
            # self.screen is a Surface
            self.screen = pygame.display.set_mode(size)

        # make a black Surface the size of the screen - used for all_sprites.clear
        # this could be replaced with a background image Surface
        self.background = pygame.Surface(size)
        self.background.fill((0, 0, 0))

        self.sprite_map: dict[str, AbstractSprite] = dict()

        self.ghost_player: Optional[GhostPlayer] = None

        if self.server:
            self.player = None

            # make Groups
            self.gems = self.create_gems()
            # in the future, add other human players to this group
            self.characters = pygame.sprite.Group()

            # special type of Group that allows only rendering "dirty" areas of the screen
            # this is unnecessary for modern hardware, which should be able to
            # redraw the whole screen each frame without struggling
            self.all_sprites = pygame.sprite.RenderUpdates(*self.characters.sprites(),
                                                           *self.gems.sprites())
        else:
            self.player = Player(self, str(uuid.uuid1()), username)
            self.ghost_player = GhostPlayer.from_spritedata(self, self.player.report())
            self.sprite_map[self.player.sprite_id] = self.player
            self.characters = pygame.sprite.Group(self.player)
            self.gems = pygame.sprite.Group()
            self.all_sprites = None

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

        if data["version"] > VERSION:
            print(
                f'Server report advanced version v{data["version"]}. Please update the client')
            return

    async def startup_client(self, server_addr):
        """Connect to the server and start game loop"""
        # set self.running to False (through exit_game) to end the game
        self.running = True

        async with websockets.connect(f'ws://{server_addr}') as ws:
            # Verify version match with server
            await ws.send(json.dumps({
                "version": VERSION
            }))

            hello = json.loads(await ws.recv())
            self.check_message(hello)

            if "state" not in hello:
                print(f'Server "{server_addr}" did not send initial game state')
                return

            self.initialize_state(hello["state"])

            game_loop = asyncio.create_task(self.run_client(ws))

            await game_loop

    async def run_client(self, ws):
        """Call this method to start the game loop."""
        while self.running:
            await self.loop_client(ws)
            await asyncio.sleep(0)

    async def loop_client(self, ws):
        """Run all aspects of one frame for the client."""
        self.player.update()

        await ws.send(json.dumps({
            "version": VERSION,
            "player_state": self.player.report()
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
            if not isinstance(winner, Character):
                raise ValueError("bad winner!")

            print("You" if winner is self.player else winner.username,
                  f"won with a score of {winner.score}!")

        self.clock.tick(FPS)

    async def loop_server(self, ws, client_update: str):
        """Run all aspects of one frame for the server."""
        self.handle_events()
        self.handle_collisions()

        # call each sprite's update method
        self.all_sprites.update()

        data = SpriteData.from_json(client_update)

        self.sprite_map[data.sprite_id].update_spritedata(data)

        # if no gem sprites remain, quit
        if not self.gems:
            winner = sorted(self.characters.sprites(), key=lambda c: c.score, reverse=True)[0]
            if not isinstance(winner, Character):
                raise ValueError("bad winner!")
            await ws.send(json.dumps(
                {
                    "version": VERSION,
                    "state": self.report_state(),
                    "winner": winner.sprite_id,
                }
            ))
            self.exit_game()

        await ws.send(json.dumps(
            {
                "version": VERSION,
                "state": self.report_state()
            }
        ))

        self.clock.tick(FPS)

    def handle_events(self):
        """Run pygame.event.pump() and close upon window close."""
        # listen for new keyboard and mouse events
        pygame.event.pump()

        # quit if the OS asks the window to close
        if pygame.QUIT in [e.type for e in pygame.event.get()]:
            self.exit_game()

    def handle_collisions(self):
        """
        Detect sprite collisions and act appropriately.

        I suppose this will eventually be handled by the server, unless we decide
        to trust clients to check their own collisions and send those to the server.
        """
        for character, gems in pygame.sprite.groupcollide(self.characters,
                                                          self.gems,
                                                          False,
                                                          False).items():
            for gem in gems:
                # if the gem hasn't already been picked up
                if gem.until_dead > 0:
                    # handles scoring and other collision logic
                    gem.on_collide(character)

    def report_state(self) -> str:
        """Report game state to be sent to the client"""
        all_sprites = [sprite.report() for sprite in self.sprite_map.values()]
        return SpriteDataGroup(all_sprites).to_json()

    def initialize_state(self, state_json: str):
        """Initialize game state from server"""
        state: SpriteDataGroup = SpriteDataGroup.from_json(state_json)
        for sprite_data in state.data:
            if sprite_data.score is None and sprite_data.owner_id is not None:
                # gem data
                gem = Gem.from_spritedata(self, sprite_data)
                self.gems.add(gem)
                self.sprite_map[sprite_data.sprite_id] = gem
            elif sprite_data.owner_id is None and sprite_data.score is not None:
                # character data
                if sprite_data.sprite_id == self.player.sprite_id:
                    self.ghost_player = GhostPlayer.from_spritedata(self, sprite_data)
                else:
                    player = OtherPlayer.from_spritedata(self, sprite_data)
                    self.characters.add(player)
                    self.sprite_map[sprite_data.sprite_id] = player
            else:
                raise ValueError("invalid sprite data")
        self.all_sprites = pygame.sprite.RenderUpdates(*self.characters.sprites(),
                                                       *self.gems.sprites())

    def update_state(self, state_json: str):
        """Update game state from server"""
        if not state_json:
            # no state; probably in the first second of the game
            return
        state: SpriteDataGroup = SpriteDataGroup.from_json(state_json)
        for sprite_data in state.data:
            if sprite_data.score is None and sprite_data.owner_id is not None:
                # gem data
                self.sprite_map[sprite_data.sprite_id].update_spritedata(sprite_data)
            elif sprite_data.owner_id is None and sprite_data.score is not None:
                # character data
                if sprite_data.sprite_id == self.player.sprite_id:
                    self.ghost_player.update_spritedata(sprite_data)
                else:
                    self.sprite_map[sprite_data.sprite_id].update_spritedata(sprite_data)
            else:
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

    def create_gems(self):
        """Return a Group of Game.GEM_NUMBER gems."""
        gems = pygame.sprite.Group()
        for _ in range(Game.GEM_NUMBER):
            gem = Gem(self, str(uuid.uuid1()))
            self.sprite_map[gem.sprite_id] = gem
            gems.add(gem)
        return gems

    def exit_game(self):
        """Stop the game after the current loop finishes."""
        self.running = False


def main():
    """Function that runs the game."""
    # parse CLI arguments
    ap = argparse.ArgumentParser(description='Game of Lag')
    ap.add_argument('-s', '--server', default='localhost')
    ap.add_argument('-p', '--port', type=int, default=7890)
    args = ap.parse_args()

    # initialize all pygame modules
    pygame.init()

    game = Game()
    asyncio.run(game.startup_client(f'{args.server}:{args.port}'))


if __name__ == "__main__":
    main()
