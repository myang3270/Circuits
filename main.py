from collections import deque
import pygame
import circuits
import math

pygame.init()

# --------------
# --- CONFIG ---
# --------------

WIDTH, HEIGHT = 900, 600
CELL = 40
SCROLL_SPEED = 40
BACKGROUND_COLOR = (255, 255, 255)
GRID_COLOR = (175, 175, 175)

# ------------
# --- INIT ---
# ------------

screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
camera_x = 0
camera_y = 0
running = True

battery_sprite = pygame.image.load("sprites/battery.png").convert_alpha()
battery_sprite = pygame.transform.scale(battery_sprite, (16, 16))
wire_sprite = pygame.image.load("sprites/wire.png").convert_alpha()
wire_sprite = pygame.transform.scale(wire_sprite, (CELL, 3))
lamp_sprite = pygame.image.load("sprites/lamp_off.png").convert_alpha()
lamp_sprite = pygame.transform.scale(lamp_sprite, (64, 48))
inv_sprite = pygame.image.load("sprites/inv.png").convert_alpha()
inv_sprite = pygame.transform.scale(inv_sprite, (64, 48))

sprites = {
    circuits.Tool.BATTERY: battery_sprite,
    circuits.Tool.WIRE: wire_sprite,
    circuits.Tool.LAMP: lamp_sprite,
    circuits.Tool.INV: inv_sprite,
}

nodes = {}
node_rotations = {}
edges = {}
selected = circuits.Tool.BATTERY

on_nodes = set()
on_edges = set()

# --------------
# --- HELPER ---
# --------------

# --- SNAP TO GRID ---
def screen_to_world(mx, my):
    return mx + camera_x, my + camera_y

def nearest_node(wx, wy):
    return round(wx / CELL), round(wy / CELL)

def nearest_edge(wx, wy):
    d1, d2 = math.floor((wx + wy) / CELL) + 0.5, math.floor((wx - wy) / CELL) + 0.5
    return (d1 + d2)/2, (d1 - d2)/2

def nearest_any(wx, wy):
    node = nearest_node(wx, wy)
    edge = nearest_edge(wx, wy)
    if get_dist(node, (wx, wy)) < get_dist(edge, (wx, wy)):
        return node
    else:
        return edge

def get_dist(x, y):
    return (x[0] - y[0]) ** 2 + (x[1] - y[1]) ** 2

def delete_at(wx, wy):
    node = nearest_node(wx, wy)
    edge = nearest_edge(wx, wy)
    if get_dist(node, (wx, wy)) < get_dist(edge, (wx, wy)):
        if node in nodes:
            nodes.pop(node)
    else:
        if edge in edges:
            edges.pop(edge)

def place_at_mouse(mx, my):
    if selected == circuits.Tool.WIRE:
        edges[nearest_edge(*screen_to_world(mx, my))] = selected
    elif selected:
        target = nearest_node(*screen_to_world(mx, my))
        if nodes.get(target, 0) != selected:
            nodes[target] = selected
            node_rotations[target] = 0
        else:
            node_rotations[target] += 1
    else:
        delete_at(*screen_to_world(mx, my))

# --- DISPLAYS ---
def draw_sprite_centered(screen, sprite, x, y, alpha=255):
    image = sprite.copy()
    image.set_alpha(alpha)

    rect = image.get_rect(center=(x, y))
    screen.blit(image, rect)

# --- BFS ---
def wired_neighbors(node):
    x, y = node
    candidates = [(x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y)]
    return [c for c in candidates if edge_key_exists(c, node)]

def edge_between(a, b):
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2

def edge_key_exists(a, b):
    return edges.get(edge_between(a, b), 0) == circuits.Tool.WIRE

def dir_from_rotation(rot):
    return [
        (0, -1),
        (1, 0),
        (0, 1),
        (-1, 0),
    ][rot % 4]

def inverter_output_neighbor(pos):
    dx, dy = dir_from_rotation(node_rotations.get(pos, 0))
    return pos[0] + dx, pos[1] + dy

def inverter_input_neighbors(pos):
    output = inverter_output_neighbor(pos)
    return [
        n for n in wired_neighbors(pos)
        if n != output
    ]

def can_wire_propagate(a, b):
    if b in nodes and nodes[b] == circuits.Tool.INV:
        return a != inverter_output_neighbor(b)

    if a in nodes and nodes[a] == circuits.Tool.INV:
        return b == inverter_output_neighbor(a)

    return True

# ------------
# --- LOOP ---
# ------------

while running:

    # ---------------
    # --- CIRCUIT ---
    # ---------------

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_a:
                camera_x -= SCROLL_SPEED

            elif event.key == pygame.K_d:
                camera_x += SCROLL_SPEED

            elif event.key == pygame.K_w:
                camera_y -= SCROLL_SPEED

            elif event.key == pygame.K_s:
                camera_y += SCROLL_SPEED

            elif event.key == pygame.K_0:
                selected = None

            elif event.key == pygame.K_1:
                selected = circuits.Tool.BATTERY

            elif event.key == pygame.K_2:
                selected = circuits.Tool.WIRE

            elif event.key == pygame.K_3:
                selected = circuits.Tool.LAMP

            elif event.key == pygame.K_4:
                selected = circuits.Tool.INV

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                place_at_mouse(*event.pos)

    # ---------------
    # --- SIGNALS ---
    # ---------------

    on_nodes = set()
    on_edges = set()


    def is_checkpoint(pos):
        return nodes.get(pos) == circuits.Tool.INV


    def spread_from_sources(node_sources, directed_edge_sources):
        reached_nodes = set(node_sources)
        reached_directed_edges = set(directed_edge_sources)

        q_nodes = deque(node_sources)
        q_edges = deque(directed_edge_sources)

        while q_nodes or q_edges:
            while q_nodes:
                pos = q_nodes.popleft()

                if is_checkpoint(pos):
                    continue

                for n in wired_neighbors(pos):
                    directed = (pos, n)

                    if directed not in reached_directed_edges:
                        reached_directed_edges.add(directed)
                        q_edges.append(directed)

            while q_edges:
                a, b = q_edges.popleft()

                if b not in reached_nodes:
                    reached_nodes.add(b)

                    if not is_checkpoint(b):
                        q_nodes.append(b)

        return reached_nodes, reached_directed_edges


    inv_on = set()

    for _ in range(20):
        old_inv_on = inv_on.copy()

        node_sources = set()
        directed_edge_sources = set()

        # batteries emit from their node
        for pos, kind in nodes.items():
            if kind == circuits.Tool.BATTERY:
                node_sources.add(pos)

        # ON inverters emit only forward
        for pos in old_inv_on:
            out = inverter_output_neighbor(pos)

            if edge_key_exists(pos, out):
                directed_edge_sources.add((pos, out))

        on_nodes, directed_on_edges = spread_from_sources(
            node_sources,
            directed_edge_sources
        )

        inv_on = set()

        for pos, kind in nodes.items():
            if kind != circuits.Tool.INV:
                continue

            out = inverter_output_neighbor(pos)

            input_on = False

            for n in wired_neighbors(pos):
                if n == out:
                    continue

                # signal must be traveling INTO this inverter
                if (n, pos) in directed_on_edges:
                    input_on = True
                    break

            if not input_on:
                inv_on.add(pos)
                on_nodes.add(pos)

        if inv_on == old_inv_on:
            break

    # convert directed edges back to normal edge positions for drawing
    on_edges = {
        edge_between(a, b)
        for (a, b) in directed_on_edges
    }

    # ---------------
    # --- DISPLAY ---
    # ---------------

    screen.fill(BACKGROUND_COLOR)

    offset_x = -camera_x % CELL
    offset_y = -camera_y % CELL

    x = offset_x
    while x < WIDTH:
        pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, HEIGHT))
        x += CELL

    y = offset_y
    while y < HEIGHT:
        pygame.draw.line(screen, GRID_COLOR, (0, y), (WIDTH, y))
        y += CELL

    # ------------------
    # --- COMPONENTS ---
    # ------------------

    for (gx, gy), kind in edges.items():
        sx = gx * CELL - camera_x
        sy = gy * CELL - camera_y
        if int(gx) == gx:
            rotated = pygame.transform.rotate(sprites[kind], 90)
        else:
            rotated = pygame.transform.rotate(sprites[kind], 0)

        draw_sprite_centered(screen, rotated, sx, sy)

    for (gx, gy), kind in nodes.items():
        sx = gx * CELL - camera_x
        sy = gy * CELL - camera_y

        display_sprite = sprites[kind]
        if kind == circuits.Tool.LAMP and (gx, gy) in on_nodes:
            display_sprite = pygame.image.load("sprites/lamp_on.png").convert_alpha()
            display_sprite = pygame.transform.scale(display_sprite, (64, 48))

        display_sprite = pygame.transform.rotate(display_sprite, -90 * node_rotations.get((gx, gy), 0))
        draw_sprite_centered(screen, display_sprite, sx, sy)

    # --- HOVER EFFECT ---

    mx, my = pygame.mouse.get_pos()
    wx, wy = screen_to_world(mx, my)

    if selected:
        display_sprite = sprites[selected]

        if selected == circuits.Tool.WIRE:
            gx, gy = nearest_edge(wx, wy)
            if int(gx) == gx:
                display_sprite = pygame.transform.rotate(display_sprite, 90)
        else:
            gx, gy = nearest_node(wx, wy)
    else:
        display_sprite = pygame.image.load("sprites/del.png").convert_alpha()
        display_sprite = pygame.transform.scale(display_sprite, (64, 48))
        gx, gy = nearest_any(wx, wy)

    sx = gx * CELL - camera_x
    sy = gy * CELL - camera_y

    draw_sprite_centered(screen, display_sprite, sx, sy, 120)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()