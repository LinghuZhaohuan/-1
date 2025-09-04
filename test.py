import os
import sys
import random
import time
import subprocess


def ensure_pygame_installed() -> None:
    """Ensure pygame is available. If missing, install it quietly at runtime."""
    try:
        import pygame  # noqa: F401
        return
    except Exception:
        pass

    python_exe = sys.executable or "python3"
    try:
        print("[setup] Installing pygame...", flush=True)
        subprocess.check_call([python_exe, "-m", "pip", "install", "--quiet", "pygame>=2.3,<3"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except Exception as exc:
        print(f"[setup] Failed to install pygame automatically: {exc}")
        print("You can manually install it with: pip install pygame")
        raise


def safe_import_pygame():
    """Import pygame after attempting installation, and set safe env defaults."""
    # Hide the default pygame support prompt
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    # Avoid audio init errors on systems without audio
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    # If no display (e.g., headless Linux), try dummy video so we can at least smoke test
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    ensure_pygame_installed()
    import pygame  # type: ignore
    return pygame


def run_tetris() -> None:
    pygame = safe_import_pygame()
    pygame.init()

    # Game constants
    grid_columns = 10
    grid_rows = 20
    block_size = 30
    play_width = grid_columns * block_size
    play_height = grid_rows * block_size

    side_panel_width = 220
    margin = 20

    window_width = play_width + side_panel_width + margin * 3
    window_height = play_height + margin * 2

    top_left_x = margin
    top_left_y = margin

    window = pygame.display.set_mode((window_width, window_height))
    pygame.display.set_caption("Tetris - Python (Arrow keys: move, Up: rotate, Space: hard drop)")

    # Colors
    black = (15, 15, 18)
    gray = (40, 45, 52)
    light_gray = (90, 100, 110)
    white = (240, 240, 245)

    colors = {
        "I": (0, 240, 240),
        "O": (240, 240, 0),
        "T": (160, 0, 240),
        "S": (0, 240, 0),
        "Z": (240, 0, 0),
        "J": (0, 0, 240),
        "L": (240, 160, 0),
    }

    # Shape definitions as 4x4 templates per rotation
    SHAPES = {
        "S": [
            [".11.", "11..", "....", "...."],
            [".1..", ".11.", "..1.", "...."],
        ],
        "Z": [
            ["11..", ".11.", "....", "...."],
            ["..1.", ".11.", ".1..", "...."],
        ],
        "I": [
            [".1111.", "......", "......", "......"],
            ["..1...", "..1...", "..1...", "..1..."],
        ],
        "O": [
            [".11.", ".11.", "....", "...."],
        ],
        "J": [
            ["1...", "111.", "....", "...."],
            [".11.", ".1..", ".1..", "...."],
            ["....", "111.", "..1.", "...."],
            [".1..", ".1..", "11..", "...."],
        ],
        "L": [
            ["..1.", "111.", "....", "...."],
            [".1..", ".1..", ".11.", "...."],
            ["....", "111.", "1...", "...."],
            ["11..", ".1..", ".1..", "...."],
        ],
        "T": [
            [".1..", "111.", "....", "...."],
            [".1..", ".11.", ".1..", "...."],
            ["....", "111.", ".1..", "...."],
            [".1..", "11..", ".1..", "...."],
        ],
    }

    # Fix shapes to ensure each rotation is 4 rows strings of equal length
    def normalize_shape(shape_rotations):
        normalized = []
        for rot in shape_rotations:
            width = max(len(row) for row in rot)
            padded = [row.ljust(width, ".") for row in rot]
            # Ensure 4 rows
            while len(padded) < 4:
                padded.append("." * width)
            normalized.append(padded[:4])
        return normalized

    SHAPES = {k: normalize_shape(v) for k, v in SHAPES.items()}

    class Piece:
        def __init__(self, x: int, y: int, shape_key: str):
            self.x = x
            self.y = y
            self.shape_key = shape_key
            self.rotations = SHAPES[shape_key]
            self.rotation_index = 0
            self.color = colors[shape_key]

        @property
        def matrix(self):
            return self.rotations[self.rotation_index % len(self.rotations)]

    def create_grid(locked):
        grid = [[black for _ in range(grid_columns)] for _ in range(grid_rows)]
        for (x, y), color in locked.items():
            if 0 <= y < grid_rows and 0 <= x < grid_columns:
                grid[y][x] = color
        return grid

    def convert_shape_format(piece: Piece):
        positions = []
        matrix = piece.matrix
        for i, line in enumerate(matrix):
            for j, char in enumerate(line):
                if char == "1":
                    positions.append((piece.x + j, piece.y + i))
        return positions

    def valid_space(piece: Piece, grid, dx=0, dy=0, rotation_delta=0):
        tentative_piece = Piece(piece.x, piece.y, piece.shape_key)
        tentative_piece.rotation_index = piece.rotation_index + rotation_delta
        positions = convert_shape_format(tentative_piece)
        for x, y in positions:
            if x < 0 or x >= grid_columns or y >= grid_rows:
                return False
            if y >= 0 and grid[y][x] != black:
                return False
        # Apply movement after bounds check
        tentative_piece.x += dx
        tentative_piece.y += dy
        positions = convert_shape_format(tentative_piece)
        for x, y in positions:
            if x < 0 or x >= grid_columns or y >= grid_rows:
                return False
            if y >= 0 and grid[y][x] != black:
                return False
        return True

    def check_lost(locked):
        for (_, y) in locked.keys():
            if y < 1:
                return True
        return False

    def get_shape():
        shape_key = random.choice(list(SHAPES.keys()))
        # Spawn in the middle-top
        # Compute shape width from current rotation 0
        rot0 = SHAPES[shape_key][0]
        rot_width = max(len(row) for row in rot0)
        x = grid_columns // 2 - rot_width // 2
        y = -2  # allow spawn above visible area
        return Piece(x, y, shape_key)

    def draw_text(surface, text, size, color, x, y, center=False):
        font = pygame.font.SysFont("consolas,menlo,dejavusansmono,couriernew", size, bold=False)
        label = font.render(text, True, color)
        rect = label.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        surface.blit(label, rect)

    def draw_grid(surface, grid):
        for y in range(grid_rows):
            for x in range(grid_columns):
                pygame.draw.rect(
                    surface,
                    grid[y][x],
                    (top_left_x + x * block_size, top_left_y + y * block_size, block_size, block_size),
                )
        # Grid lines
        for y in range(grid_rows + 1):
            pygame.draw.line(
                surface,
                gray,
                (top_left_x, top_left_y + y * block_size),
                (top_left_x + play_width, top_left_y + y * block_size),
                1,
            )
        for x in range(grid_columns + 1):
            pygame.draw.line(
                surface,
                gray,
                (top_left_x + x * block_size, top_left_y),
                (top_left_x + x * block_size, top_left_y + play_height),
                1,
            )

        # Border
        pygame.draw.rect(
            surface,
            light_gray,
            (top_left_x - 2, top_left_y - 2, play_width + 4, play_height + 4),
            2,
        )

    def clear_rows(grid, locked):
        cleared = 0
        for y in range(grid_rows - 1, -1, -1):
            if black not in grid[y]:
                cleared += 1
                # remove all locked blocks in this row
                for x in range(grid_columns):
                    try:
                        del locked[(x, y)]
                    except KeyError:
                        pass
                # shift rows above down
                for (x, yy) in sorted(list(locked.keys()), key=lambda p: p[1]):
                    if yy < y:
                        color = locked[(x, yy)]
                        del locked[(x, yy)]
                        locked[(x, yy + 1)] = color
        return cleared

    def draw_next(surface, piece: Piece):
        x0 = top_left_x + play_width + margin
        y0 = top_left_y
        draw_text(surface, "Next:", 24, white, x0, y0)
        y0 += 28
        # draw at small scale
        preview_block = int(block_size * 0.8)
        matrix = piece.rotations[0]
        for i, row in enumerate(matrix):
            for j, char in enumerate(row):
                if char == "1":
                    pygame.draw.rect(
                        surface,
                        piece.color,
                        (
                            x0 + j * preview_block,
                            y0 + i * preview_block,
                            preview_block,
                            preview_block,
                        ),
                    )

    def draw_stats(surface, score, level, lines):
        x0 = top_left_x + play_width + margin
        y0 = top_left_y + 160
        draw_text(surface, f"Score: {score}", 24, white, x0, y0)
        y0 += 30
        draw_text(surface, f"Level: {level}", 24, white, x0, y0)
        y0 += 30
        draw_text(surface, f"Lines: {lines}", 24, white, x0, y0)

        y0 += 30
        draw_text(surface, "Controls:", 22, white, x0, y0)
        y0 += 24
        for line in [
            "←/→ move",
            "↑ rotate",
            "↓ soft drop",
            "Space hard drop",
            "P pause, R restart",
            "Q quit",
        ]:
            draw_text(surface, line, 18, light_gray, x0, y0)
            y0 += 20

    def hard_drop(piece: Piece, grid, locked):
        distance = 0
        while True:
            tentative = Piece(piece.x, piece.y + 1, piece.shape_key)
            tentative.rotation_index = piece.rotation_index
            if valid_space(tentative, grid):
                piece.y += 1
                distance += 1
            else:
                break
        # lock immediately
        for x, y in convert_shape_format(piece):
            if y >= 0:
                locked[(x, y)] = piece.color
        return distance

    def lock_piece(piece: Piece, locked):
        for x, y in convert_shape_format(piece):
            if y >= 0:
                locked[(x, y)] = piece.color

    def get_level(lines_cleared_total: int) -> int:
        return 1 + lines_cleared_total // 10

    def gravity_delay_seconds(level: int) -> float:
        # Classic-like gravity curve
        return max(0.08, 0.8 - (level - 1) * 0.07)

    clock = pygame.time.Clock()

    locked_positions = {}
    grid = create_grid(locked_positions)

    current_piece = get_shape()
    next_piece = get_shape()

    score = 0
    total_lines = 0
    level = get_level(total_lines)

    fall_time_acc = 0.0
    fall_delay = gravity_delay_seconds(level)
    running = True
    paused = False

    last_drop_soft_time = 0.0

    def draw_everything():
        window.fill((22, 25, 30))
        draw_text(window, "Tetris", 36, white, top_left_x + play_width + margin, top_left_y)
        draw_grid(window, grid)
        # Draw current piece
        for x, y in convert_shape_format(current_piece):
            if y >= 0:
                pygame.draw.rect(
                    window,
                    current_piece.color,
                    (top_left_x + x * block_size, top_left_y + y * block_size, block_size, block_size),
                )
        draw_next(window, next_piece)
        draw_stats(window, score, level, total_lines)
        if paused:
            draw_text(window, "Paused", 42, white, top_left_x + play_width // 2, top_left_y + play_height // 2, center=True)
        pygame.display.update()

    while running:
        dt_ms = clock.tick(60)
        dt = dt_ms / 1000.0
        fall_time_acc += dt

        # Recompute gravity per current level
        fall_delay = gravity_delay_seconds(level)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_r:
                    # Restart
                    return run_tetris()
                if paused:
                    continue
                if event.key == pygame.K_LEFT:
                    tentative = Piece(current_piece.x - 1, current_piece.y, current_piece.shape_key)
                    tentative.rotation_index = current_piece.rotation_index
                    if valid_space(tentative, grid):
                        current_piece.x -= 1
                elif event.key == pygame.K_RIGHT:
                    tentative = Piece(current_piece.x + 1, current_piece.y, current_piece.shape_key)
                    tentative.rotation_index = current_piece.rotation_index
                    if valid_space(tentative, grid):
                        current_piece.x += 1
                elif event.key == pygame.K_UP:
                    tentative = Piece(current_piece.x, current_piece.y, current_piece.shape_key)
                    tentative.rotation_index = current_piece.rotation_index + 1
                    # Simple wall kick: try shifts -1, +1 if rotation collides
                    shifts = [0, -1, 1, -2, 2]
                    for s in shifts:
                        if valid_space(tentative, grid, dx=s):
                            current_piece.rotation_index += 1
                            current_piece.x += s
                            break
                elif event.key == pygame.K_DOWN:
                    # Soft drop one cell
                    tentative = Piece(current_piece.x, current_piece.y + 1, current_piece.shape_key)
                    tentative.rotation_index = current_piece.rotation_index
                    if valid_space(tentative, grid):
                        current_piece.y += 1
                        score += 1  # soft drop point
                        last_drop_soft_time = time.time()
                elif event.key == pygame.K_SPACE:
                    dropped = hard_drop(current_piece, grid, locked_positions)
                    score += 2 * dropped
                    grid = create_grid(locked_positions)
                    cleared = clear_rows(grid, locked_positions)
                    if cleared:
                        total_lines += cleared
                        gained = {1: 100, 2: 300, 3: 500, 4: 800}.get(cleared, 100 * cleared)
                        score += gained * level
                        level = get_level(total_lines)
                    current_piece = next_piece
                    next_piece = get_shape()

        if paused:
            draw_everything()
            continue

        # Natural gravity
        if fall_time_acc >= fall_delay:
            fall_time_acc = 0.0
            tentative = Piece(current_piece.x, current_piece.y + 1, current_piece.shape_key)
            tentative.rotation_index = current_piece.rotation_index
            if valid_space(tentative, grid):
                current_piece.y += 1
            else:
                # lock piece
                lock_piece(current_piece, locked_positions)
                grid = create_grid(locked_positions)
                cleared = clear_rows(grid, locked_positions)
                if cleared:
                    total_lines += cleared
                    gained = {1: 100, 2: 300, 3: 500, 4: 800}.get(cleared, 100 * cleared)
                    score += gained * level
                    level = get_level(total_lines)
                current_piece = next_piece
                next_piece = get_shape()
                # Check game over
                if check_lost(locked_positions):
                    draw_text(window, "Game Over", 48, white, top_left_x + play_width // 2, top_left_y + play_height // 2 - 20, center=True)
                    draw_text(window, "Press R to restart, Q to quit", 24, white, top_left_x + play_width // 2, top_left_y + play_height // 2 + 20, center=True)
                    pygame.display.update()
                    # Wait for user decision
                    waiting = True
                    while waiting:
                        for e in pygame.event.get():
                            if e.type == pygame.QUIT:
                                waiting = False
                                running = False
                            elif e.type == pygame.KEYDOWN:
                                if e.key == pygame.K_q:
                                    waiting = False
                                    running = False
                                elif e.key == pygame.K_r:
                                    return run_tetris()
                        clock.tick(30)

        # Update grid with current piece shadow
        grid = create_grid(locked_positions)
        for x, y in convert_shape_format(current_piece):
            if y >= 0:
                grid[y][x] = current_piece.color

        draw_everything()

    pygame.quit()


def _headless_smoke_test():
    """Run a very small headless test if no display is available."""
    pygame = safe_import_pygame()
    try:
        pygame.display.init()
        surf = pygame.Surface((100, 100))
        surf.fill((255, 0, 0))
        pygame.draw.rect(surf, (0, 255, 0), (10, 10, 80, 80), 3)
        pygame.display.quit()
        print("Headless smoke test OK. To play, run in a GUI environment.")
    except Exception as exc:
        print(f"Headless smoke test failed: {exc}")


if __name__ == "__main__":
    # If running in a true headless Linux environment without DISPLAY, do a smoke test instead of launching the game
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and os.environ.get("SDL_VIDEODRIVER") == "dummy":
        _headless_smoke_test()
    else:
        run_tetris()

import sys

print(sys.path)