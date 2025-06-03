import pygame
from os.path import join
from random import randint, uniform
import pickle
import neat
import os
import sys

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
        # Cooldown
        self.can_shoot = True
        self.laser_shoot_time = 0
        self.cooldown_duration = 400

        self.laser_surf = laser_surf
        self.laser_group = laser_group
        self.all_sprites = all_sprites

    def external_update(self, action, dt):
        # action: [move_x, move_y, shoot]
        self.direction.x = action[0]
        self.direction.y = action[1]
        if self.direction.length_squared() > 0:
            self.direction = self.direction.normalize()
        self.rect.center += self.direction * self.speed * dt

        # Impede sair da tela
        self.rect.clamp_ip(pygame.Rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT))

        if action[2] and self.can_shoot:
            Laser(self.laser_surf, self.rect.midtop,
                  (self.all_sprites, self.laser_group))
            self.can_shoot = False
            self.laser_shoot_time = pygame.time.get_ticks()

        self.laser_timer()

    def laser_timer(self):
        if not self.can_shoot:
            current_time = pygame.time.get_ticks()
            if current_time - self.laser_shoot_time >= self.cooldown_duration:
                self.can_shoot = True


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
    def __init__(self, surf, pos, groups):
        super().__init__(groups)
        self.original_surf = surf
        self.image = self.original_surf
        self.rect = self.image.get_frect(center=pos)
        self.start_time = pygame.time.get_ticks()
        self.life_time = 3000
        self.direction = pygame.Vector2(uniform(-0.5, 0.5), 1)
        self.speed = randint(400, 500)
        self.rotation = 0
        self.rotation_speed = randint(40, 80)

    def update(self, dt):
        self.rect.center += self.direction * self.speed * dt
        if pygame.time.get_ticks() - self.start_time >= self.life_time:
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

        self.clock = pygame.time.Clock()
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
        self.meteor_timer = 0

    def step(self, action, dt):
        self.player.external_update(action, dt)
        self.all_sprites.update(dt)
        self._collisions()
        self._spawn_meteors(dt)
        self.score += dt

    def _spawn_meteors(self, dt):
        self.meteor_timer += dt
        if self.meteor_timer > 0.2:
            x, y = randint(0, WINDOW_WIDTH), randint(-200, -100)
            Meteor(self.meteor_surf, (x, y),
                   (self.all_sprites, self.meteor_sprites))
            self.meteor_timer = 0

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
                AnimatedExplosion(self.explosion_frames,
                                  laser.rect.midtop, self.all_sprites)

    def get_state(self):
        px, py = self.player.rect.center

        # Lista de (dist, dx, dy, vx, vy)
        meteors = []
        for m in self.meteor_sprites:
            mx, my = m.rect.center
            dx, dy = mx - px, my - py
            dist = (dx*dx + dy*dy)**0.5
            vx, vy = m.direction.x * m.speed, m.direction.y * m.speed
            meteors.append((dist, dx / WINDOW_WIDTH, dy /
                           WINDOW_HEIGHT, vx / 500, vy / 500))

        meteors.sort(key=lambda x: x[0])
        N = 8
        state = [
            px / WINDOW_WIDTH * 2 - 1,
            py / WINDOW_HEIGHT * 2 - 1,
        ]
        # Adiciona dados dos N meteoros mais próximos
        for i in range(N):
            if i < len(meteors):
                _, dx, dy, vx, vy = meteors[i]
                state += [dx, dy, vx, vy]
            else:
                # Preenche com zeros se não houver meteoro suficiente
                state += [0, 0, 0, 0]

        # Adiciona info se pode atirar (1 se sim, 0 se não)
        state.append(1.0 if self.player.can_shoot else 0.0)

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

    MAX_STEPS = 60 * 30  # 30 segundos a 60 FPS

    for genome_id, genome in genomes:
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        game = SpaceShooterGame(render=False)
        games.append(game)
        nets.append(net)
        ge.append(genome)
        genome.fitness = 0

    alive = [True]*len(games)
    steps = 0  # inicializa aqui!

    while any(alive) and steps < MAX_STEPS:
        for i, game in enumerate(games):
            if not alive[i]:
                continue
            if not game.running and alive[i]:
                alive[i] = False
                continue

            state = game.get_state()
            output = nets[i].activate(state)
            move_x = 1 if output[0] > 0.5 else (-1 if output[0] < -0.5 else 0)
            move_y = 1 if output[1] > 0.5 else (-1 if output[1] < -0.5 else 0)
            shoot = 1 if output[2] > 0.5 else 0
            game.step([move_x, move_y, shoot], dt)

            # FITNESS
            ge[i].fitness += dt * 0.5
            ge[i].fitness += game.meteors_destroyed * 5.0
            game.meteors_destroyed = 0

            if abs(game.player.direction.x) < 0.01 and abs(game.player.direction.y) < 0.01:
                ge[i].fitness -= dt * 0.1  # Penalidade leve mas constante

            margin = 100
            px, py = game.player.rect.center
            if px < margin or px > WINDOW_WIDTH - margin or py < margin or py > WINDOW_HEIGHT - margin:
                ge[i].fitness -= dt * 2.0

            move_mag = abs(game.player.direction.x) + \
                abs(game.player.direction.y)
            ge[i].fitness += move_mag * dt * 0.05

            if ge[i].fitness < 0:
                ge[i].fitness = 0

        steps += 1  # <<<<<<<< MOVA PARA FORA DO FOR!

# --- Treinamento NEAT ---


def run_neat(config_file):
    config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                         neat.DefaultSpeciesSet, neat.DefaultStagnation,
                         config_file)
    # config = neat.Config(
    #     neat.DefaultGenome,
    #     neat.DefaultReproduction,
    #     neat.DefaultSpeciesSet,
    #     neat.DefaultStagnation,
    #     config_file
    # )
    p = neat.Population(config)
    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)

    winner = p.run(eval_genomes, 50)  # 50 gerações

    with open("best_genome.pkl", "wb") as f:
        pickle.dump(winner, f)
    print("Melhor genoma salvo em best_genome.pkl")

# --- Visualizar o melhor agente ---


def play_best(config_file, genome_file):
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
    clock = pygame.time.Clock()
    while game.running:
        dt = clock.tick(60)/1000
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
