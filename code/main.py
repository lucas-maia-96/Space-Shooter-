import pygame
from os.path import join 
from random import randint

# general setup 
pygame.init()
WINDOW_WIDTH, WINDOW_HEIGHT = 1280, 720
display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption('Space Shooter')
running = True

# Plain Surface

surf = pygame.Surface((100,200))
surf.fill('orange')
x = 100

#Importing an image
player_surf = pygame.image.load(join('images', 'player.png')).convert_alpha()
star_surf = pygame.image.load(join('images', 'star.png')).convert_alpha()
star_pos = [(randint(10, 1270), randint(10, 710)) for i in range(20)]


while running:
    # Event loop
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # draw the game
    display_surface.fill('black')
    for pos in star_pos:
        display_surface.blit(star_surf, pos)
    x+=0.1
    display_surface.blit(player_surf, (x,150))
    pygame.display.update()


pygame.quit()
