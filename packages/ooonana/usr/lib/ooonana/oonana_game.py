#!/usr/bin/env python3
"""
oonana - Ooonana OS Breakout Minigame
Installer game engine. Bricks spell "OOONANA OS". Ball is the Ooonana face.
"""
import os
import random
import select
import sys
import termios
import time
import tty

WIDTH = 80
HEIGHT = 26

BRICKS_MAP = [
    "  OOO   OOO   OOO  N   N  AAAA  N   N  AAAA    OOO   SSS ",
    " O   O O   O O   O NN  N A    A NN  N A    A  O   O S    ",
    " O   O O   O O   O N N N AAAAAA N N N AAAAAA  O   O  SSS ",
    " O   O O   O O   O N  NN A    A N  NN A    A  O   O     S",
    "  OOO   OOO   OOO  N   N A    A N   N A    A   OOO   SSS ",
]

COLOR = os.environ.get("NO_COLOR", "") == ""
COLORS = {
    "O": "\033[1;33m",
    "N": "\033[1;36m",
    "A": "\033[1;32m",
    "S": "\033[1;35m",
}
RESET = "\033[0m"

BALL_FACES = {
    "up": "(^_^)",
    "down": "('.')",
    "bounce": "(o_o)",
    "death": "(x_x)",
    "win": "(^o^)",
}


def color(code, text):
    if not COLOR:
        return text
    return f"{code}{text}{RESET}"


class Game:
    def __init__(self):
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.victory = False
        self.paddle_x = (WIDTH - 12) // 2
        self.ball_x = 40.0
        self.ball_y = 17.0
        self.ball_vx = random.choice([-0.5, 0.5])
        self.ball_vy = -0.5
        self.bounce_timer = 0
        self.death_timer = 0
        self.combo = 0
        self.bricks = [list(row) for row in BRICKS_MAP]

    def reset_ball(self):
        self.ball_x = 40.0
        self.ball_y = 17.0
        self.ball_vx = random.choice([-0.5, 0.5])
        self.ball_vy = -0.5
        self.death_timer = 20
        self.combo = 0

    def ball_face(self):
        if self.death_timer > 0:
            self.death_timer -= 1
            return BALL_FACES["death"]
        if self.bounce_timer > 0:
            self.bounce_timer -= 1
            return BALL_FACES["bounce"]
        if self.ball_vy < 0:
            return BALL_FACES["up"]
        return BALL_FACES["down"]

    def check_victory(self):
        return all(char == " " for row in self.bricks for char in row)

    def step(self, key):
        if key == "quit":
            return False
        if key == "left":
            self.paddle_x = max(1, self.paddle_x - 3)
        elif key == "right":
            self.paddle_x = min(WIDTH - 13, self.paddle_x + 3)

        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy

        if self.ball_x <= 3:
            self.ball_x = 3.0
            self.ball_vx = abs(self.ball_vx)
            self.bounce_timer = 5
        elif self.ball_x >= WIDTH - 4:
            self.ball_x = float(WIDTH - 4)
            self.ball_vx = -abs(self.ball_vx)
            self.bounce_timer = 5

        if self.ball_y <= 2:
            self.ball_y = 2.0
            self.ball_vy = abs(self.ball_vy)
            self.bounce_timer = 5

        by = int(self.ball_y)
        bx = int(self.ball_x)
        if 3 <= by <= 7:
            brick_row = by - 3
            hit = False
            for delta in range(-2, 3):
                col = bx + delta - 12
                if 0 <= col < len(BRICKS_MAP[0]) and self.bricks[brick_row][col] != " ":
                    self.bricks[brick_row][col] = " "
                    self.combo += 1
                    self.score += 10 * min(self.combo, 5)
                    hit = True
            if hit:
                self.ball_vy = -self.ball_vy
                self.bounce_timer = 5
                self.victory = self.check_victory()

        if int(self.ball_y) == 22 and int(self.paddle_x) <= int(self.ball_x) <= int(self.paddle_x) + 12:
            self.ball_vy = -abs(self.ball_vy)
            hit_pos = (self.ball_x - self.paddle_x) / 12.0
            self.ball_vx = 1.2 * (hit_pos - 0.5)
            self.bounce_timer = 5
            self.combo = 0

        if self.ball_y > 23:
            self.lives -= 1
            self.combo = 0
            if self.lives <= 0:
                self.game_over = True
            else:
                self.reset_ball()
        return True

    def render(self):
        buffer = []
        header = (
            f" Ooonana OS Breakout  Bricks: OOONANA OS  "
            f"Score: {self.score}  Lives: {self.lives}  combo:{self.combo} "
        )
        buffer.append(color("\033[1;33m", header.center(WIDTH, " ")))
        buffer.append(color("\033[1;33m", "=" * WIDTH))

        face = self.ball_face()
        for y in range(2, HEIGHT - 1):
            line = [" "] * WIDTH
            line[0] = color("\033[1;33m", "|")
            line[WIDTH - 1] = color("\033[1;33m", "|")

            if 3 <= y <= 7:
                brick_row = y - 3
                for x in range(WIDTH):
                    col = x - 12
                    if 0 <= col < len(BRICKS_MAP[0]):
                        char = self.bricks[brick_row][col]
                        if char != " ":
                            line[x] = color(COLORS.get(char, "\033[1;33m"), char)

            if y == 22:
                for x in range(int(self.paddle_x), int(self.paddle_x) + 12):
                    if 0 < x < WIDTH - 1:
                        line[x] = color("\033[1;33m", "#")

            if y == int(self.ball_y):
                start = int(self.ball_x) - len(face) // 2
                for index, char in enumerate(face):
                    pos = start + index
                    if 0 < pos < WIDTH - 1:
                        line[pos] = color("\033[1;32m", char)

            buffer.append("".join(line))

        buffer.append(color("\033[1;33m", "=" * WIDTH))
        footer = " A/D or arrow keys move | Q quit "
        buffer.append(color("\033[1;32m", footer.center(WIDTH, " ")))
        return "\n".join(buffer)


def usage():
    print(
        """oonana

Ooonana brickout.
Installer game engine.
Bricks spell OOONANA OS.
Ball sprite: Ooonana face ball.
real-time Python terminal game with combo scoring.

Keys:
  use a/d or arrow keys
  a / left arrow   left
  d / right arrow  right
  q      quit

Options:
  --snapshot       render one frame, useful for tests
  -h, --help       show help
"""
    )


def get_key():
    if select.select([sys.stdin], [], [], 0.02)[0]:
        char = sys.stdin.read(1)
        if char == "\x1b":
            if select.select([sys.stdin], [], [], 0.05)[0]:
                seq = sys.stdin.read(2)
                if seq == "[D":
                    return "left"
                if seq == "[C":
                    return "right"
            return "quit"
        if char in ("a", "A"):
            return "left"
        if char in ("d", "D"):
            return "right"
        if char in ("q", "Q", "\x03"):
            return "quit"
    return None


def snapshot():
    game = Game()
    print(game.render())
    data = sys.stdin.read(1)
    if data.lower() == "q":
        print(f"bye. score:{game.score}")


def run():
    game = Game()
    old_settings = None
    sys.stdout.write("\033[?25l\033[2J")
    sys.stdout.flush()
    try:
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        while not game.game_over and not game.victory:
            key = get_key()
            if key == "quit":
                break
            game.step(key)
            sys.stdout.write("\033[H" + game.render())
            sys.stdout.flush()
            time.sleep(0.03)
    finally:
        if old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h\033[0m\n")
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
