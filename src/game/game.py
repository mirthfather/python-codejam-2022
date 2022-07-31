import asyncio
import json
import random
from typing import Tuple, Union

import numpy as np
import pygame
import websockets

# width and height of the screen in pixels
# a fullscreen window of variable size would be possible
WIDTH = 640
HEIGHT = 480

# target frames per second
FPS = 60


class AbstractSprite(pygame.sprite.Sprite):
    """An abstract class for shared code between Gem and Character."""

    def __init__(self, width, height, color):
        super().__init__()

        # image is a specially recognized Sprite attribute
        # for now, it is a solid color, but pygame.image.load returns an image as a Surface
        self.image = pygame.Surface((width, height))
        self.image.fill(color)

        # rect is also a specially recognized Sprite attribute
        self.rect = self.image.get_rect()


class Character(AbstractSprite):
    """A character controlled by a player."""

    # pixels per second per second, converted to pixels per frame per frame
    THRUST = 50 * FPS**(-2)

    WIDTH = 25
    HEIGHT = 25

    COLOR = (255, 0, 0)

    def __init__(self, color: Tuple[int] = None):
        super().__init__(Character.WIDTH,
                         Character.HEIGHT,
                         Character.COLOR if color is None else color)

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


class Player(Character):
    """A Character that can be controlled locally by the keyboard."""

    COLOR = (0, 255, 255)

    def __init__(self):
        super().__init__(color=Player.COLOR)

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

    def __init__(self):
        super().__init__(Gem.WIDTH, Gem.HEIGHT, Gem.COLOR)

        # place the Gem in a random spot on the screen
        self.rect.center = (random.randint(Gem.WIDTH/2, WIDTH-(Gem.WIDTH/2)),
                            random.randint(Gem.HEIGHT/2, HEIGHT-(Gem.HEIGHT/2)))

        # number of frames until gem is picked up by a character
        self.until_dead = Gem.PICKUP_TIME
        # used to track if the owner has left
        self.prev_until_dead = self.until_dead
        self.dead_timer = Gem.DEAD_TIME

        self.owner: Union[Character, None] = None

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
        self.image.fill(Gem.DEAD_COLOR)
        # make the gem opaque
        self.image.set_alpha(255)


class Game(object):
    """Object to handle all game-level tasks."""

    # how many gems to start the game with
    GEM_NUMBER = 10

    def __init__(self):
        self.running = False
        # make the window for the game
        # self.screen is a Surface
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

        # make a black Surface the size of the screen - used for all_sprites.clear
        # this could be replaced with a background image Surface
        self.background = pygame.Surface(self.screen.get_size())
        self.background.fill((0, 0, 0))

        self.player = Player()

        # make Groups
        self.gems = self.create_gems()
        # in the future, add other human players to this group
        self.characters = pygame.sprite.Group(self.player)

        # special type of Group that allows only rendering "dirty" areas of the screen
        # this is unnecessary for modern hardware, which should be able to
        # redraw the whole screen each frame without struggling
        self.all_sprites = pygame.sprite.RenderUpdates(*self.characters.sprites(), *self.gems.sprites())

        self.clock = pygame.time.Clock()

    async def startup(self):
        """Connect to the server and start game loop"""
        # set self.running to False (through exit_game) to end the game
        self.running = True
        server_host = 'de.jjolly.dev:7890'

        async with websockets.connect(f'ws://{server_host}') as ws:
            # Verify version match with server
            await ws.send(json.dumps({
                "version": 1.0
            }))

            hello = json.loads(await ws.recv())
            if "error" in hello:
                print(f'Server "{server_host}" failed connection with error: {hello["error"]}')
                return

            if "version" not in hello:
                print(f'Server "{server_host}" did not send version identifier')
                return

            if hello["version"] > 1.0:
                print(f'Server "{server_host}" report advanced version v{hello["version"]}. Please update the client')
                return

            game_loop = asyncio.create_task(self.run())

            await game_loop

    async def run(self):
        """Call this method to start the game loop."""
        while self.running:
            self.loop()
            await asyncio.sleep(0)

    def loop(self):
        """Run all aspects of one frame."""
        self.handle_events()
        self.handle_collisions()

        # call each sprite's update method
        self.all_sprites.update()

        # if no gem sprites remain, quit
        if not self.gems:
            winner = sorted(self.characters.sprites(), key=lambda c: c.score, reverse=True)[0]
            print("You" if winner == self.player else winner, f"won with a score of {winner.score}!")
            self.exit_game()

        self.render()

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
            gems.add(Gem())
        return gems

    def exit_game(self):
        """Stop the game after the current loop finishes."""
        self.running = False


def main():
    """Function that runs the game."""
    # initialize all pygame modules
    pygame.init()

    game = Game()
    asyncio.run(game.startup())


if __name__ == "__main__":
    main()
