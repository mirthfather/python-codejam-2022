"""Abstract classes for shared code everywhere."""

import pygame
import time
from typing import List

VERSION = 1.0


def timestamp() -> float:
    """
    Return a float number of seconds representing the current time.

    The time elapsed between two points can be obtained by determining the
    difference between what this function returned at two different times.
    """
    return time.clock_gettime(time.CLOCK_REALTIME)


class SpriteMap(pygame.sprite.Group):
    """A derivative of pygame.sprite.Group that can return sprites by UUID."""

    def __getitem__(self, uuid: str) -> pygame.sprite.Sprite:
        for sprite in self.spritedict:
            if sprite.sprite_id == uuid:
                return sprite
        raise KeyError(f"no sprite with id {uuid}")

    def ids(self) -> List[str]:
        """Return the UUIDs of each sprite."""
        return [sprite.sprite_id for sprite in self.spritedict]


class SpriteTracker:
    """
    Base class that stores shared code from Server and Game.

    It looks like they actually share very little code, so it may be possible
    to remove this class in the future.
    """

    def __init__(self):
        # Group that can access sprites by UUID
        self.sprite_map = SpriteMap()
