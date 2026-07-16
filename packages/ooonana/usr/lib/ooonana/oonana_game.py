#!/usr/bin/env python3
"""Ooonana OS terminal brickout."""

import os
import random
import select
import sys
import time

try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None


WIDTH = 80
HEIGHT = 26
PADDLE_WIDTH = 14
PADDLE_Y = HEIGHT - 4
BRICK_TOP = 4

BRICKS_MAP = [
    "  OOO   OOO   OOO  N   N  AAAA  N   N  AAAA    OOO   SSS ",
    " O   O O   O O   O NN  N A    A NN  N A    A  O   O S    ",
    " O   O O   O O   O N N N AAAAAA N N N AAAAAA  O   O  SSS ",
    " O   O O   O O   O N  NN A    A N  NN A    A  O   O     S",
    "  OOO   OOO   OOO  N   N A    A N   N A    A   OOO   SSS ",
]

LOGO_BALL = [
    " __________   ",
    " |  _    _  | ",
    " | / \\  / \\ | ",
    "/|   \\__/   |\\",
    " |__________| ",
    "    |    |    ",
]

BALL_FACES = {
    "normal": LOGO_BALL,
    "hit": [
        " __________   ",
        " |  >    <  | ",
        " |          | ",
        "/|   \\__/   |\\",
        " |__________| ",
        "    |    |    ",
    ],
    "death": [
        " __________   ",
        " |  x    x  | ",
        " |          | ",
        "/|    __    |\\",
        " |__________| ",
        "    |    |    ",
    ],
}

COLOR_ENABLED = os.environ.get("NO_COLOR", "") == ""
RESET = "\033[0m"
YELLOW = "\033[1;33m"
CYAN = "\033[1;36m"
GREEN = "\033[1;32m"
MAGENTA = "\033[1;35m"
WHITE = "\033[1;37m"
BRICK_COLORS = {"O": YELLOW, "N": CYAN, "A": GREEN, "S": MAGENTA}
SPEED_DELAYS = {1: 0.055, 2: 0.036, 3: 0.022}


def color(code, text):
    if not COLOR_ENABLED:
        return text
    return f"{code}{text}{RESET}"


class Game:
    def __init__(self, speed=2):
        self.speed = speed
        self.restart()

    def restart(self):
        self.score = 0
        self.lives = 3
        self.combo = 0
        self.paused = False
        self.game_over = False
        self.victory = False
        self.paddle_x = (WIDTH - PADDLE_WIDTH) // 2
        self.bricks = [list(row) for row in BRICKS_MAP]
        self.reset_ball(initial=True)

    def reset_ball(self, initial=False):
        self.ball_x = WIDTH / 2
        self.ball_y = 15.0
        self.ball_vx = random.choice((-0.58, 0.58))
        self.ball_vy = -0.48
        self.effect = "normal" if initial else "death"
        self.effect_ticks = 0 if initial else 12
        self.combo = 0

    @property
    def ball_half_width(self):
        return max(len(line) for line in LOGO_BALL) // 2

    @property
    def ball_top(self):
        return int(round(self.ball_y)) - len(LOGO_BALL) // 2

    @property
    def ball_bottom(self):
        return self.ball_top + len(LOGO_BALL) - 1

    def ball_face(self):
        if self.effect_ticks > 0:
            self.effect_ticks -= 1
            return BALL_FACES[self.effect]
        self.effect = "normal"
        return BALL_FACES["normal"]

    def set_hit_effect(self):
        self.effect = "hit"
        self.effect_ticks = 4

    def check_victory(self):
        return not any(char != " " for row in self.bricks for char in row)

    def handle_key(self, key):
        if key == "quit":
            return False
        if key == "restart":
            self.restart()
            return True
        if key == "pause":
            self.paused = not self.paused
            return True
        if key in ("speed1", "speed2", "speed3"):
            self.speed = int(key[-1])
            return True
        if key == "left":
            self.paddle_x = max(1, self.paddle_x - 4)
        elif key == "right":
            self.paddle_x = min(WIDTH - PADDLE_WIDTH - 1, self.paddle_x + 4)
        return True

    def hit_bricks(self):
        if self.ball_vy >= 0:
            probe_y = self.ball_bottom
        else:
            probe_y = self.ball_top
        brick_bottom = BRICK_TOP + len(BRICKS_MAP) - 1
        if not BRICK_TOP <= probe_y <= brick_bottom:
            return False

        brick_row = probe_y - BRICK_TOP
        brick_start = (WIDTH - len(BRICKS_MAP[0])) // 2
        ball_left = int(round(self.ball_x)) - self.ball_half_width
        ball_right = int(round(self.ball_x)) + self.ball_half_width
        hits = []
        for screen_x in range(ball_left, ball_right + 1):
            col = screen_x - brick_start
            if 0 <= col < len(self.bricks[brick_row]) and self.bricks[brick_row][col] != " ":
                hits.append(col)

        for col in hits[:3]:
            self.bricks[brick_row][col] = " "
            self.combo += 1
            self.score += 10 * min(self.combo, 5)
        if hits:
            self.ball_vy = -self.ball_vy
            self.set_hit_effect()
            self.victory = self.check_victory()
            return True
        return False

    def step(self, key=None):
        if not self.handle_key(key):
            return False
        if self.paused or self.game_over or self.victory:
            return True

        previous_bottom = self.ball_bottom
        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy

        min_x = 1 + self.ball_half_width
        max_x = WIDTH - 2 - self.ball_half_width
        if self.ball_x < min_x:
            self.ball_x = float(min_x)
            self.ball_vx = abs(self.ball_vx)
            self.set_hit_effect()
        elif self.ball_x > max_x:
            self.ball_x = float(max_x)
            self.ball_vx = -abs(self.ball_vx)
            self.set_hit_effect()

        min_y = 3 + len(LOGO_BALL) // 2
        if self.ball_top < 3:
            self.ball_y = float(min_y)
            self.ball_vy = abs(self.ball_vy)
            self.set_hit_effect()

        self.hit_bricks()

        ball_left = self.ball_x - self.ball_half_width
        ball_right = self.ball_x + self.ball_half_width
        paddle_right = self.paddle_x + PADDLE_WIDTH - 1
        if (
            self.ball_vy > 0
            and previous_bottom < PADDLE_Y <= self.ball_bottom
            and ball_right >= self.paddle_x
            and ball_left <= paddle_right
        ):
            self.ball_y -= max(0, self.ball_bottom - PADDLE_Y + 1)
            self.ball_vy = -abs(self.ball_vy)
            hit_position = (self.ball_x - self.paddle_x) / PADDLE_WIDTH
            self.ball_vx = max(-0.82, min(0.82, (hit_position - 0.5) * 1.5))
            self.combo = 0
            self.set_hit_effect()

        if self.ball_top > PADDLE_Y + 1:
            self.lives -= 1
            if self.lives <= 0:
                self.game_over = True
            else:
                self.reset_ball()
        return True

    def render_lines(self):
        state = "PAUSED" if self.paused else "PLAY"
        header = (
            f"Ooonana OS Breakout | OOONANA OS | Score:{self.score} | Lives:{self.lives} "
            f"| combo:{self.combo} | Speed: {self.speed} | {state}"
        )
        lines = [color(YELLOW, header[:WIDTH].center(WIDTH)), color(CYAN, "=" * WIDTH)]
        face = self.ball_face()
        brick_start = (WIDTH - len(BRICKS_MAP[0])) // 2
        sprite_top = self.ball_top

        for y in range(2, HEIGHT - 1):
            line = [" "] * WIDTH
            line[0] = color(YELLOW, "|")
            line[-1] = color(YELLOW, "|")

            if BRICK_TOP <= y < BRICK_TOP + len(self.bricks):
                row = self.bricks[y - BRICK_TOP]
                for col, char in enumerate(row):
                    x = brick_start + col
                    if char != " " and 0 < x < WIDTH - 1:
                        line[x] = color(BRICK_COLORS.get(char, WHITE), char)

            if y == PADDLE_Y:
                paddle = "[" + "=" * (PADDLE_WIDTH - 2) + "]"
                for offset, char in enumerate(paddle):
                    line[self.paddle_x + offset] = color(CYAN, char)

            if sprite_top <= y < sprite_top + len(face):
                sprite_line = face[y - sprite_top]
                sprite_left = int(round(self.ball_x)) - len(sprite_line) // 2
                for offset, char in enumerate(sprite_line):
                    x = sprite_left + offset
                    if char != " " and 0 < x < WIDTH - 1:
                        line[x] = color(GREEN, char)

            lines.append("".join(line))

        lines.append(color(CYAN, "=" * WIDTH))
        footer = " A/D or arrows move | P pause | R restart | 1/2/3 speed | Q quit "
        lines.append(color(MAGENTA, footer.center(WIDTH)))
        return lines

    def render(self):
        return "\n".join(self.render_lines())


def render_diff(lines, previous):
    chunks = []
    for row, line in enumerate(lines, start=1):
        if previous is None or row > len(previous) or line != previous[row - 1]:
            chunks.append(f"\033[{row};1H{line}")
    return "".join(chunks)


def usage():
    print(
        """oonana

Ooonana brickout.
Installer game engine.
Bricks spell OOONANA OS.
Ball sprite: full Ooonana logo ball.
real-time Python terminal game with combo scoring and smooth row updates.

Keys:
  a/d or arrow keys   move
  p      pause
  r      restart
  1/2/3  speed
  q      quit

Options:
  --snapshot       render one deterministic test frame
  -h, --help       show help
"""
    )


def get_key(timeout):
    if not select.select([sys.stdin], [], [], timeout)[0]:
        return None
    char = sys.stdin.read(1)
    if char == "\x1b":
        if select.select([sys.stdin], [], [], 0.04)[0]:
            sequence = sys.stdin.read(2)
            if sequence == "[D":
                return "left"
            if sequence == "[C":
                return "right"
        return None
    return {
        "a": "left",
        "A": "left",
        "d": "right",
        "D": "right",
        "p": "pause",
        "P": "pause",
        "r": "restart",
        "R": "restart",
        "1": "speed1",
        "2": "speed2",
        "3": "speed3",
        "q": "quit",
        "Q": "quit",
        "\x03": "quit",
    }.get(char)


def snapshot():
    random.seed(7)
    game = Game()
    print(game.render())
    if not sys.stdin.isatty() and sys.stdin.read(1).lower() == "q":
        print(f"bye. score:{game.score}")


def run():
    if termios is None or tty is None:
        snapshot()
        return
    game = Game()
    previous = None
    old_settings = None
    sys.stdout.write("\033[?25l\033[2J")
    sys.stdout.flush()
    try:
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        while not game.game_over and not game.victory:
            key = get_key(SPEED_DELAYS[game.speed])
            if key == "quit":
                break
            game.step(key)
            lines = game.render_lines()
            sys.stdout.write(render_diff(lines, previous))
            sys.stdout.flush()
            previous = lines
    finally:
        if old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        sys.stdout.write(f"\033[{HEIGHT + 3};1H\033[?25h\033[0m\n")
        sys.stdout.flush()

    if game.victory:
        print(f"VICTORY. score:{game.score}")
    elif game.game_over:
        print(f"GAME OVER. score:{game.score}")
    else:
        print(f"bye. score:{game.score}")


def main():
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        usage()
        return
    if "--snapshot" in sys.argv[1:] or not sys.stdin.isatty() or not sys.stdout.isatty():
        snapshot()
        return
    run()


if __name__ == "__main__":
    main()
