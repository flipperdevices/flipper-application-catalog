# Maze 3D

A first-person 3D raycasting maze game for Flipper Zero, tuned for the 128×64 monochrome display.

## Features

- **3D raycasting engine** — distance shading, wall-orientation brightness, dithered floor/ceiling.
- **Three modes**
  - **Campaign** — 1–10 pure maze, 11–20 items + puzzle, 21+ enemies + combat. Difficulty auto-scales. Level select: cleared levels replayable, uncleared locked.
  - **Endless** — find the exit to descend. Pick any starting floor. Strict size cap + always-on compass prevents flicker/crash.
  - **Visitor** — free roam with NPCs wandering the maze.
- **Inventory** — long-press OK in-game. Key (opens doors), Torch, Potion (restore HP), Amulet (warp to start).
- **Compass + minimap** — always points to the exit.
- **Bilingual UI** — switch Chinese / English any time in the menu (← / →).
- **Auto save** — campaign progress and endless floor persisted.
- **Opening animation + SFX** — skippable intro with BGM; speaker sound effects throughout.
- **Performance** — half-resolution raycasting (64 cols), on-demand ~8 Hz world tick, 12 KB stack.

## Controls

| Key | In-game | In-menu |
| --- | --- | --- |
| Up / Down | Move forward / backward | Move cursor |
| Left / Right | Turn left / right | Switch language |
| OK (short) | Interact / dash | Confirm |
| OK (long) | Open inventory | — |
| Back (short) | Pause | Back |
| Back (long) | Exit to home | Exit |

## Install

Copy `maze3d.fap` to `apps/Games/` on the Flipper's SD card, or sideload via qFlipper.

Prebuilt binary: https://github.com/k20120509/flipper-release/releases/tag/v4.4.0

## Source

https://github.com/k20120509/flipper-release

MIT
