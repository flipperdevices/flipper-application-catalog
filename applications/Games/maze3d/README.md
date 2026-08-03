# Maze 3D

A first-person 3D raycasting maze game for Flipper Zero, tuned for the 128×64 monochrome display. Features a Minecraft-inspired sandbox mode with day/night cycle, particle effects, and a full campaign with combat.

## Features

- **3D raycasting engine** — distance shading, wall-orientation brightness, dithered floor/ceiling, global brightness boost.
- **Four modes**
  - **Campaign** — 1–10 pure maze, 11–20 puzzle (keys + doors), 21–50 combat (guns + enemies). Difficulty auto-scales. Level select: cleared levels replayable, uncleared locked.
  - **Endless** — find the exit to descend. Pick any starting floor.
  - **Visitor** — free roam with NPCs wandering the maze.
  - **Minecraft Sandbox** — pure flatland building mode with day/night cycle, 12 block textures, mining + placing.
- **Combat system** — shooting with particle effects (sparks, explosions, bullet trails, dust). Enemies with AI (chase + ranged shooting). 2-second invincibility after hit, 1 HP/sec regen.
- **Health system** — base 10 HP, scales with level (max 20). Invincibility frames + auto regen.
- **Minecraft mode** — 12 textured blocks (grass, dirt, sand, wood, log, stone, brick, water, leaves, metal, vine, torch). Water animation, day/night cycle with sun/moon arc, starfield at night.
- **Particle system** — 32-particle pool: shooting sparks, hit explosions, bullet trails, walking dust, block-break debris.
- **Contrast crosshair** — XOR-rendered crosshair always visible against any background.
- **World caching** — pre-generated mazes saved to App Data for instant loading.
- **BFS pathfinding** — maze generation uses BFS to guarantee solvable mazes (no dead-ends).
- **Bilingual UI** — switch Chinese / English any time in the menu.
- **Auto save** — campaign progress, endless floor, achievements, and world cache persisted.
- **Opening animation + SFX** — intro with BGM; speaker sound effects throughout.

## Controls (Maze modes)

| Key | In-game | In-menu |
| --- | --- | --- |
| Up / Down | Move forward / backward | Move cursor |
| Left / Right | Turn left / right | Switch language |
| OK (short) | Shoot | Confirm |
| OK (long) | Open inventory | — |
| Back (short) | Pause | Back |
| Back (long) | Exit to home | Exit |

## Controls (Minecraft mode)

| Key | Action |
| --- | --- |
| Up / Down | Move forward / backward |
| Left / Right | Turn left / right |
| OK (short) | Place block |
| OK (long) | Mine block |
| Back (short) | Switch held block |
| Back (long) | Exit to menu |

## Block types (Minecraft mode)

Brick, Stone, Wood, Grass, Dirt, Sand, Log, Leaves — 8 placeable blocks with unique textures.

## Install

Copy `maze3d.fap` to `apps/Games/` on the Flipper's SD card, or sideload via qFlipper.

Prebuilt binary: https://github.com/k20120509/flipper-release/releases/tag/v6.6

## Source

https://github.com/k20120509/flipper-release

MIT
