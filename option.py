import pygame
from os.path import join
from random import randint, uniform, seed as pyseed
import random
import pickle
import neat
import os
import sys
import math

if len(sys.argv) == 2 and sys.argv[1] == "train":
    os.environ["SDL_VIDEODRIVER"] = "dummy"

pygame.init()
pygame.display.set_mode((1, 1))  # Cria contexto de vídeo oculto

WINDOW_WIDTH, WINDOW_HEIGHT = 1280, 720


class Player(pygame.sprite.Sprite):
    def __init__(self, groups, laser_surf, laser_group, all_sprites):
        super().__init__(groups)
        self.image = pygame.image.load(
            join('images', 'player.png')).convert_alpha()
        self.rect = self.image.get_frect(
            center=(WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2))
        self.direction = pygame.math.Vector2()
        self.speed = 300
        self.can_shoot = True
        self.laser_cooldown = 0.0  # cooldown em segundos
        self.cooldown_duration = 0.4  # 400 ms = 0.4 s

        self.laser_surf = laser_surf
        self.laser_group = laser_group
        self.all_sprites = all_sprites

    def external_update(self, action, dt):
        self.direction.x = action[0]
        self.direction.y = action[1]
        if self.direction.length_squared() > 0:
            self.direction = self.direction.normalize()
        self.rect.center += self.direction * self.speed * dt

        # Impede sair da tela
        self.rect.clamp_ip(pygame.Rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT))

        # Cooldown local
        if not self.can_shoot:
            self.laser_cooldown -= dt
            if self.laser_cooldown <= 0:
                self.can_shoot = True

        if action[2] and self.can_shoot:
            Laser(self.laser_surf, self.rect.midtop,
                  (self.all_sprites, self.laser_group))
            self.can_shoot = False
            self.laser_cooldown = self.cooldown_duration


class Star(pygame.sprite.Sprite):
    def __init__(self, groups, surf):
        super().__init__(groups)
        self.image = surf
        self.rect = self.image.get_frect(
            center=(randint(0, WINDOW_WIDTH), randint(0, WINDOW_HEIGHT)))


class Laser(pygame.sprite.Sprite):

    def __init__(self, surf, pos, groups):
        super().__init__(groups)
        self.image = surf
        self.rect = self.image.get_frect(midbottom=pos)

    def update(self, dt):
        self.rect.centery -= 400 * dt
        if self.rect.bottom < 0:
            self.kill()


class Meteor(pygame.sprite.Sprite):
    def __init__(self, surf, pos, groups, direction=None):
        super().__init__(groups)
        self.original_surf = surf
        self.image = self.original_surf
        self.rect = self.image.get_frect(center=pos)
        self.life_time = 6.0  # segundos
        self.time_alive = 0.0
        if direction is not None:
            self.direction = direction
        else:
            self.direction = pygame.Vector2(uniform(-0.5, 0.5), 1)
        self.speed = randint(200, 250)
        self.rotation = 0
        self.rotation_speed = randint(40, 80)

    def update(self, dt):
        self.rect.center += self.direction * self.speed * dt
        self.time_alive += dt
        if self.time_alive >= self.life_time:
            self.kill()
        self.rotation += self.rotation_speed * dt
        self.image = pygame.transform.rotozoom(
            self.original_surf, self.rotation, 1)
        self.rect = self.image.get_frect(center=self.rect.center)


class AnimatedExplosion(pygame.sprite.Sprite):
    def __init__(self, frames, pos, groups):
        super().__init__(groups)
        self.frames = frames
        self.frame_index = 0
        self.image = self.frames[self.frame_index]
        self.rect = self.image.get_frect(center=pos)

    def update(self, dt):
        self.frame_index += 25 * dt
        if self.frame_index < len(self.frames):
            self.image = self.frames[int(self.frame_index)]
        else:
            self.kill()

# --- Classe principal do jogo para NEAT ---


class SpaceShooterGame:
    def __init__(self, render=False):
        self.render = render
        if render:
            self.display_surface = pygame.display.set_mode(
                (WINDOW_WIDTH, WINDOW_HEIGHT))
            pygame.display.set_caption('Space Shooter')
        else:
            self.display_surface = pygame.Surface(
                (WINDOW_WIDTH, WINDOW_HEIGHT))

        self.running = True
        self.score = 0
        self.meteors_destroyed = 0

        # Load assets
        self.star_surf = pygame.image.load(
            join('images', 'star.png')).convert_alpha()
        self.meteor_surf = pygame.image.load(
            join('images', 'meteor.png')).convert_alpha()
        self.laser_surf = pygame.image.load(
            join('images', 'laser.png')).convert_alpha()
        self.font = pygame.font.Font(join('images', 'Oxanium-Bold.ttf'), 20)
        self.explosion_frames = [pygame.image.load(
            join('images', 'explosion', f'{i}.png')).convert_alpha() for i in range(21)]

        # Sprite groups
        self.all_sprites = pygame.sprite.Group()
        self.meteor_sprites = pygame.sprite.Group()
        self.laser_sprites = pygame.sprite.Group()

        for _ in range(20):
            Star(self.all_sprites, self.star_surf)

        self.player = Player(self.all_sprites, self.laser_surf,
                             self.laser_sprites, self.all_sprites)
        self.meteor_timer = 0.0

    def step(self, action, dt):
        self.player.external_update(action, dt)
        self.all_sprites.update(dt)
        self._collisions()
        self._spawn_meteors(dt)
        self.score += dt

    def _spawn_meteors(self, dt):
        self.meteor_timer += dt
        if self.meteor_timer > 0.5:
            px, py = self.player.rect.center  # Posição atual do player

            if random.random() < 0.1:  # 10% dos meteoros miram o player
                x = random.choice([0, WINDOW_WIDTH])
                y = randint(-200, -100)
                direction = pygame.Vector2(px - x, py - y).normalize()
                Meteor(self.meteor_surf, (x, y), (self.all_sprites,
                       self.meteor_sprites), direction=direction)
            else:
                x, y = randint(0, WINDOW_WIDTH), randint(-200, -100)
                Meteor(self.meteor_surf, (x, y),
                       (self.all_sprites, self.meteor_sprites))
            self.meteor_timer = 0.0

    def _collisions(self):
        collision_sprites = pygame.sprite.spritecollide(
            self.player, self.meteor_sprites, True, pygame.sprite.collide_mask)
        if collision_sprites:
            self.running = False

        for laser in self.laser_sprites:
            collided_sprites = pygame.sprite.spritecollide(
                laser, self.meteor_sprites, True)
            if collided_sprites:
                laser.kill()
                self.meteors_destroyed += len(collided_sprites)
                if self.render:
                    AnimatedExplosion(self.explosion_frames,
                                      laser.rect.midtop, self.all_sprites)

    # def get_state(self):
    #     px, py = self.player.rect.center

    #     meteors = []
    #     for m in self.meteor_sprites:
    #         mx, my = m.rect.center
    #         dx, dy = mx - px, my - py
    #         dist = (dx*dx + dy*dy)**0.5
    #         vx, vy = m.direction.x * m.speed, m.direction.y * m.speed
    #         meteors.append((dist, dx / WINDOW_WIDTH, dy /
    #                         WINDOW_HEIGHT, vx / 500, vy / 500))

    #     meteors.sort(key=lambda x: x[0])
    #     N = 8
    #     state = [
    #         px / WINDOW_WIDTH * 2 - 1,
    #         py / WINDOW_HEIGHT * 2 - 1,
    #     ]
    #     for i in range(N):
    #         if i < len(meteors):
    #             _, dx, dy, vx, vy = meteors[i]
    #             state += [dx, dy, vx, vy]
    #         else:
    #             state += [0, 0, 0, 0]

    #     state.append(1.0 if self.player.can_shoot else 0.0)
    #     return state

    def get_state(self):
        px, py = self.player.rect.center
        num_sectors = 16
        max_dist = math.hypot(WINDOW_WIDTH, WINDOW_HEIGHT)
        radar = [0.0] * num_sectors  # Inicializa com 0 (sem meteoro)

        for m in self.meteor_sprites:
            mx, my = m.rect.center
            dx, dy = mx-px, my-py
            angle = (math.atan2(dy, dx) + 2*math.pi) % (2*math.pi)
            dist = math.hypot(dx, dy)
            sector = int(angle // (2 * math.pi / num_sectors))
            # Quanto mais perto, maior valor
            norm_dist = 1.0 - min(dist/max_dist, 1.0)
            if radar[sector] < norm_dist:
                radar[sector] = norm_dist

        # Estado final: posição normalizada do player + radar + pode atirar
        state = [
            px / WINDOW_WIDTH * 2 - 1,
            py / WINDOW_HEIGHT * 2 - 1,
            *radar,
            1.0 if self.player.can_shoot else 0.0
        ]

        return state

    def draw(self):
        if not self.render:
            return
        self.display_surface.fill('#04010f')
        self.all_sprites.draw(self.display_surface)
        pygame.display.update()

    def quit(self):
        pygame.quit()

# --- Função de avaliação para o NEAT ---


def eval_genomes(genomes, config):

    dt = 1/60
    games = []
    nets = []
    ge = []

    MAX_STEPS = 60 * 90  # 30 segundos a 60 FPS

    for genome_id, genome in genomes:
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        game = SpaceShooterGame(render=False)
        games.append(game)
        nets.append(net)
        ge.append(genome)
        genome.fitness = 0

    alive = [True]*len(games)
    steps = 0

    while any(alive) and steps < MAX_STEPS:
        for i, game in enumerate(games):
            if not alive[i]:
                continue
            if not game.running and alive[i]:
                ge[i].fitness -= 5
                alive[i] = False
                continue

            state = game.get_state()
            output = nets[i].activate(state)
            move_x = 1 if output[0] > 0.5 else (-1 if output[0] < -0.5 else 0)
            move_y = 1 if output[1] > 0.5 else (-1 if output[1] < -0.5 else 0)
            shoot = 1 if output[2] > 0.5 else 0
            game.step([move_x, move_y, shoot], dt)

            # FITNESS
            ge[i].fitness += dt * 0.2
            ge[i].fitness += game.meteors_destroyed * 20.0
            game.meteors_destroyed = 0

            # Penaliza ficar parado
            if abs(game.player.direction.x) < 0.01 and abs(game.player.direction.y) < 0.01:
                ge[i].fitness -= dt * 0.2

            margin = 100
            px, py = game.player.rect.center
            dist_left = px
            dist_right = WINDOW_WIDTH - px
            dist_top = py
            dist_bottom = WINDOW_HEIGHT - py
            min_dist_to_edge = min(dist_left, dist_right,
                                   dist_top, dist_bottom)
            if min_dist_to_edge < margin:
                # Penaliza mais forte perto da borda
                ge[i].fitness -= dt * \
                    (2.0 + (margin - min_dist_to_edge) / margin * 3.0)

            if ge[i].fitness < 0:
                ge[i].fitness = 0

        steps += 1

# --- Treinamento NEAT ---


def run_neat(config_file):
    config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                         neat.DefaultSpeciesSet, neat.DefaultStagnation,
                         config_file)
    p = neat.Population(config)
    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)

    winner = p.run(eval_genomes, 100)

    with open("best_genome.pkl", "wb") as f:
        pickle.dump(winner, f)
    print("Melhor genoma salvo em best_genome.pkl")

    # --- Visualizar o melhor agente ---


def play_best(config_file, genome_file):
    # Semente fixa para ambiente igual ao do treino!

    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_file
    )
    with open(genome_file, "rb") as f:
        genome = pickle.load(f)
    net = neat.nn.FeedForwardNetwork.create(genome, config)
    game = SpaceShooterGame(render=True)
    # Use dt fixo para garantir física idêntica ao treino!
    dt = 1/60
    while game.running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False
        state = game.get_state()
        output = net.activate(state)
        move_x = 1 if output[0] > 0.5 else (-1 if output[0] < -0.5 else 0)
        move_y = 1 if output[1] > 0.5 else (-1 if output[1] < -0.5 else 0)
        shoot = 1 if output[2] > 0.5 else 0
        game.step([move_x, move_y, shoot], dt)
        game.draw()
    print("Score do melhor agente:", game.score)
    game.quit()

# --- Main ---


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "train":
        run_neat("config-feedforward.txt")
    elif len(sys.argv) == 2 and sys.argv[1] == "play":
        play_best("config-feedforward.txt", "best_genome.pkl")
    else:
        print("Use:\n  python space_shooter_neat.py train\n  python space_shooter_neat.py play")
