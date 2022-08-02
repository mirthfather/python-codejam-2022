"""Abstract classes for shared code everywhere."""

import pygame

# target frames per second
FPS = 60

VERSION = 1.0


class SpriteMap(pygame.sprite.Group):
    """A derivative of pygame.sprite.Group that can return sprites by UUID."""

    def __getitem__(self, uuid: str) -> pygame.sprite.Sprite:
        for sprite in self.spritedict:
            if sprite.sprite_id == uuid:
                return sprite
        raise KeyError(f"no sprite with id {uuid}")

    def ids(self) -> None:
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
