# Maze 3D / 3D 迷宫

A first-person 3D raycasting maze game for Flipper Zero.

一款为 Flipper Zero 打造的第一人称 3D 光线投射迷宫游戏。

## Features / 特性

- **3D raycasting engine** — distance shading, wall orientation brightness, dithered floor & ceiling.
- **Three game modes / 三种模式**
  - **Story / 剧情模式** — 600-word prologue with 2 branching choices affecting starting stats. 1–10 pure-maze levels, 11–20 items & puzzle, 21+ enemies & combat. Difficulty auto-scales. You can replay any cleared level; uncleared levels are locked.
  - **Endless / 无尽模式** — find the exit to descend, pick any level to enter. Strict performance cap (maze ≤21, compass always on) to prevent flicker / crash.
  - **Visitor / 游客漫游** — free roam with NPCs wandering around.
- **Inventory / 物品栏** — long-press OK in game to open, Up/Down select, OK use, Back resume. Items: Key, Torch, Potion (restore HP), Amulet (warp back to start).
- **Compass + Minimap** — compass always points to the exit, minimap shows nearby layout and items.
- **Bilingual UI / 双语界面** — switch Chinese / English any time in the menu with ← / →.
- **Auto save / 自动存档** — progress and floor number persisted across restarts.
- **Performance tuned / 性能优化** — half-resolution raycasting (64 cols), on-demand rendering (~8 Hz world tick), 8 KB stack.

## Controls / 操作

| Key / 按键 | In-game / 游戏中 | In-menu / 菜单中 |
| --- | --- | --- |
| Up | Move forward / 前进 | Move cursor / 上移 |
| Down | Move backward / 后退 | Move cursor / 下移 |
| Left | Turn left / 左转 | Switch language / 切中文 |
| Right | Turn right / 右转 | Switch language / 切英文 |
| OK (short) | Interact / 互动 | Confirm / Start / 确认 |
| OK (long) | Open Inventory / 开物品栏 | — |
| Back (short) | Pause / 暂停 | Back to menu / 返回 |
| Back (long) | Exit to home / 退出到桌面 | Exit / 退出 |

## Source / 源码

Repository: https://github.com/k20120509/flipper-release

Release + prebuilt `.fap` (copy to `apps/Games/` on the SD card):  
https://github.com/k20120509/flipper-release/releases/tag/v3.0.0

