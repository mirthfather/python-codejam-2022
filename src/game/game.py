import numpy as np
import pygame
import random

# width and height of the screen in pixels
# fullscreen window of variable size is certainly possible
WIDTH = 640
HEIGHT = 480

# target frames per second
FPS = 60


class AbstractSprite(pygame.sprite.Sprite):
    """ An abstract class for shared code between Gem and Character. """

    def __init__(self, width, height, color):
        super().__init__()

        # image is a specially recognized Sprite attribute
        # for now, it is a solid color, but pygame.image.load returns an image as a Surface
        self.image = pygame.Surface((width, height))
        self.image.fill(color)

        # rect is also a specially recognized Sprite attribute
        self.rect = self.image.get_rect()


class Gem(AbstractSprite):
    """ A gem for a character to pick up. """

    WIDTH = 10
    HEIGHT = 10

    COLOR = (0, 255, 0)

    def __init__(self):
        super().__init__(Gem.WIDTH, Gem.HEIGHT, Gem.COLOR)

        # place the Gem in a random spot on the screen
        self.rect.center = (random.randint(Gem.WIDTH / 2, WIDTH - (Gem.WIDTH / 2)),
                            random.randint(Gem.HEIGHT / 2, HEIGHT - (Gem.HEIGHT / 2)))


class Character(AbstractSprite):
    """ A character controlled by a player. """

    # pixels per second, converted to pixels per frame
    SPEED = 150 / FPS

    WIDTH = 25
    HEIGHT = 25

    COLOR = (255, 0, 0)

    def __init__(self):
        super().__init__(Character.WIDTH, Character.HEIGHT, Character.COLOR)

        # track position independently of the rect, enabling floating-point precision
        self.pos = np.array((WIDTH / 2, HEIGHT / 2))

    def update(self):
        """ Called every frame. """

        if pygame.key.get_pressed()[pygame.K_f]:
            print("f")

        # change in position (dx, dy)
        dpos = np.zeros(2)

        if pygame.key.get_pressed()[pygame.K_LEFT]:
            dpos[0] = -1
        if pygame.key.get_pressed()[pygame.K_RIGHT]:
            dpos[0] = 1
        if pygame.key.get_pressed()[pygame.K_UP]:
            dpos[1] = -1
        if pygame.key.get_pressed()[pygame.K_DOWN]:
            dpos[1] = 1

        # normalize the direction so that moving diagonally does not move faster
        # this is done by dividing the dpos by its magnitude
        # the 'or 1' causes division by 1 if the magnitude is 0 to avoid zero division errors
        dpos /= np.sqrt((dpos**2).sum()) or 1
        # now set the speed
        dpos *= Character.SPEED

        self.pos += dpos

        # prevent the character from going off the screen
        # Keep in mind that it is not the center that must not go off screen, but rather any part of the character.
        # Hence the multiple appearances of WIDTH / 2 and HEIGHT / 2.
        # These next two lines could be combined, but they are already basically unreadable as is. :P

        # set the maximum x and y to screen width and height
        self.pos = np.minimum((WIDTH-(Character.WIDTH/2), HEIGHT-(Character.HEIGHT/2)), self.pos)
        # set the minimum x and y to zero
        self.pos = np.maximum((Character.WIDTH/2, Character.HEIGHT/2), self.pos)

        # changing the rect's center automatically changes the sprite's position
        self.rect.center = self.pos


class Game(object):
    """ Object to handle all game-level tasks. """

    # how many gems to start the game with
    GEM_NUMBER = 10

    def __init__(self):
        # make the window for the game
        # self.screen is a Surface
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

        # make a black Surface the size of the screen - used for all_sprites.clear
        # this could be replaced with a background image Surface
        self.background = pygame.Surface(self.screen.get_size())
        self.background.fill((0, 0, 0))

        self.character = Character()

        # make a Group of Gem sprites
        self.gems = self.create_gems()

        # special type of Group that allows only rendering "dirty" areas of the screen
        # this is unnecessary for modern hardware, which should be able to
        # redraw the whole screen each frame without struggling
        self.all_sprites = pygame.sprite.RenderUpdates(self.character, *self.gems.sprites())

        self.clock = pygame.time.Clock()

    def run(self):
        """ Call this method to start the game loop. """
        # set self.running to False (through exit_game) to end the game
        self.running = True
        while self.running:
            self.loop()

    def loop(self):
        """ Run all aspects of one frame. """

        self.handle_events()
        self.handle_collisions()

        # call each sprite's update method
        self.all_sprites.update()

        # if no gem sprites remain, quit
        if not self.gems:
            print("You won!")
            self.exit_game()

        self.render()

        self.clock.tick(FPS)

    def handle_events(self):
        """ Run pygame.event.pump() and close upon window close. """
        # listen for new keyboard and mouse events
        pygame.event.pump()

        # quit if the OS asks the window to close
        if pygame.QUIT in [e.type for e in pygame.event.get()]:
            self.exit_game()

    def handle_collisions(self):
        """ Detect sprite collisions and act appropriately. """
        for gem in pygame.sprite.spritecollide(self.character, self.gems, dokill=True):
            print("You scored!")

    def render(self):
        """ Perform everything that needs to be done to draw all changes. """
        # clear dirty areas left by sprites' previous locations
        # comment out this line to see why it's necessary :P
        self.all_sprites.clear(self.screen, self.background)
        # draw everything
        dirty = self.all_sprites.draw(self.screen)
        # update only the areas that have changed
        pygame.display.update(dirty)

    def create_gems(self):
        """ Return a Group of Game.GEM_NUMBER gems. """
        gems = pygame.sprite.Group()
        for _ in range(Game.GEM_NUMBER):
            gems.add(Gem())
        return gems

    def exit_game(self):
        """ Stop the game after the current loop finishes. """
        self.running = False


def main():
    # initialize all pygame modules
    pygame.init()

    game = Game()
    game.run()


main()
