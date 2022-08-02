import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

import numpy as np
import pygame
from dataclasses_json import dataclass_json

import gol_abc

# For now, these are copied from game.py, but in the future, there needs to be
# some way to communicate width and height---perhaps just as arguments to
# Sprite constructors.
WIDTH = 640
HEIGHT = 480


@dataclass_json
@dataclass
class SpriteData:
    """Class to represent the current state data of a character or gem."""

    # common attributes
    sprite_id: str
    pos:       Tuple[float, float]

    # Character attributes
    username:  Optional[str]                 = field(default=None)
    score:     Optional[int]                 = field(default=None)
    thrust:    Optional[tuple[float, float]] = field(default=None)
    velocity:  Optional[tuple[float, float]] = field(default=None)

    # Gem attributes
    collision_time:   Optional[float] = field(default=None)
    owner_id:         Optional[str]   = field(default=None)


@dataclass_json
@dataclass
class SpriteDataGroup:
    """Json-(un)serializable wrapper for a list of SpriteData objects"""

    data: list[SpriteData]


class AbstractSprite(pygame.sprite.Sprite):
    """An abstract class for shared code between Gem and Character."""

    def __init__(
        self,
        sprite_id: str,
        width: int,
        height: int,
        color: pygame.Color
    ):
        super().__init__()
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

    # pixels per second per second
    THRUST = 50

    WIDTH = 25
    HEIGHT = 25

    COLOR = (255, 0, 255)

    def __init__(self, sprite_id: str, username: str, pos: Tuple[float, float]):
        super().__init__(
            sprite_id,
            self.WIDTH,
            self.HEIGHT,
            pygame.Color(*self.COLOR)
        )

        self.username = username

        # track position independently of the rect, enabling floating-point precision
        self.pos = np.array(pos, dtype=float)

        # pixels per second
        self.velocity = np.zeros(2)
        # pixels per second per second
        self.thrust = np.zeros(2)
        # timestamp of the last time move was called
        self.last_move = gol_abc.timestamp()

        self.score = 0

    def update(self):
        self.move(self.thrust)

    def move(self, thrust: np.ndarray):
        """Correct the magnitude of the thrust and move the character accordingly."""
        diff = gol_abc.timestamp() - self.last_move

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

        self.velocity += thrust * diff
        self.pos += self.velocity * diff

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

        self.last_move += diff

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
            # np arrays must be converted to floats before sending; otherwise,
            # elements have a numpy type that is not JSON serializable
            pos=tuple(map(float, self.pos)),
            # Character attributes
            username=self.username,
            velocity=tuple(map(float, self.velocity)),
            score=self.score,
        )

    @classmethod
    def from_spritedata(cls, data: SpriteData) -> 'Character':
        """
        Instantiate an object of this class for a given game using SpriteData.

        :param game: the current game
        :param data: the state to use
        :return: the new object
        """
        obj = cls(data.sprite_id, data.username, data.pos)
        obj.update_spritedata(data)
        return obj

    def update_spritedata(self, data: SpriteData) -> None:
        """
        Update the state of a sprite using SpriteData.

        :param data: the state to use
        :return: None
        """
        self.check_sprite_id(data.sprite_id)

        self.score = data.score
        # ignore pos for now---we are trying to make move client-only
        # self.pos = data.pos
        self.velocity = np.array(data.velocity)
        self.thrust = np.array(data.thrust)


class GhostPlayer(Character):
    """The ghost of the current player as reported by the server."""

    COLOR = (0, 255, 255, 127)


class Player(Character):
    """A Character that can be controlled locally by the keyboard."""

    COLOR = (0, 255, 255)

    def __init__(self, sprite_id: str, username: str):
        # start off-screen for now
        # A cleaner method would be to not make a player until we know its pos.
        # Adding that would align well with having the server assign uuids
        # instead of having clients report them.
        super().__init__(sprite_id, username, (-50, -50))

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

        self.move(thrust)

    def update_spritedata(self, data: SpriteData) -> None:
        """
        Update the state of a sprite using SpriteData.

        :param data: the state to use
        :return: None
        """
        self.check_sprite_id(data.sprite_id)
        self.score = data.score


class Gem(AbstractSprite):
    """A gem for a character to pick up."""

    WIDTH = 10
    HEIGHT = 10

    COLOR = (0, 255, 0)
    DEAD_COLOR = (255, 0, 0)

    # how long the Sprite should flash after being picked up in seconds
    DEAD_TIME = 0.5
    # how long each flash when dead is in seconds
    DEAD_FLASH_TIME = 0.15

    # how long it takes a Character to pick up a Gem in seconds
    PICKUP_TIME = 0.5

    def __init__(self,
                 game: 'Game',
                 sprite_id: str,
                 ):
        super().__init__(sprite_id, Gem.WIDTH, Gem.HEIGHT, pygame.Color(Gem.COLOR))

        self.game = game

        # place the Gem in a random spot on the screen
        self.rect.center = (random.randint(Gem.WIDTH//2, WIDTH-(Gem.WIDTH//2)),
                            random.randint(Gem.HEIGHT//2, HEIGHT-(Gem.HEIGHT//2)))

        # time when the owner started colliding with the gem
        # based on SERVER time
        self.collision_time: Union[float, None] = None
        # used to track if the owner has left
        self.collided_last_frame = False
        # time when the owner picked up the gem
        # based on CLIENT time
        self.dead_time: Union[float, None] = None

        self.owner: Union[Character, None] = None

    def update(
            self,
            collisions:       Optional[List[Character]] = None,
            server_timestamp: Optional[float]           = None
        ) -> None:
        """Called every frame."""
        # if collisions is not None or if collisions is not empty
        # and this gem has not yet been picked up
        if collisions and (self.dead_time is None):
            # if this gem is not currently being picked up
            if self.collision_time is None:
                # assign a new owner
                # in the rare event that two characters collide with a gem at the same time, we will prefer whichever one happens to be the first in the list
                self.owner = collisions[0]
                self.collision_time = server_timestamp
            # if this gem is already being picked up
            else:
                if server_timestamp - self.collision_time >= Gem.PICKUP_TIME:
                    self.die()
                    self.owner.increment_score()
        else:
            # reset the counter if the owner has left
            self.owner = None
            self.collision_time = None

        # if this gem has already been picked up
        if self.dead_time is not None:
            diff = gol_abc.timestamp() - self.dead_time
            if diff >= Gem.DEAD_TIME:
                # built-in Sprite method that removes this Sprite from all groups
                self.kill()

            # toggle transparency/opaqueness to create a flashing effect
            self.image.set_alpha(255 * (1 - ((diff // Gem.DEAD_FLASH_TIME) % 2)))

        # if this gem has not yet been picked up and we have a server timestamp
        # AND we are colliding a character
        elif server_timestamp is not None and self.collision_time is not None:
            # change transparency based on the time until the gem will be picked up
            self.image.set_alpha(((server_timestamp - self.collision_time)/Gem.PICKUP_TIME) * 255)

    def die(self) -> None:
        """Prepare for the "flashing after death" state."""
        # change the gem's color
        self.image.fill(pygame.Color(Gem.DEAD_COLOR))
        self.dead_time = gol_abc.timestamp()

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
            collision_time=self.collision_time,
            owner_id=None if self.owner is None else self.owner.sprite_id,
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
        self.collision_time = data.collision_time
        self.owner = None if data.owner_id is None else self.game.sprite_map[data.owner_id]
