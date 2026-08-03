v6.6:
- FIX: Maze dead-ends — BFS pathfinding replaces Manhattan distance for exit placement, guaranteeing solvable mazes.
- FIX: Key reachability — BFS validation ensures keys are always placed in reachable area before doors.
- FIX: Endless mode stage mismatch — was passing floor+100 causing false combat branch.
- World pre-generation cache — complete maze snapshots saved to App Data for instant loading.

v6.5:
- Health system overhaul: base 10 HP (was 5-7), +2 per 5 levels (max 20).
- 2-second invincibility after taking damage (immune to all damage during iframe).
- Auto regen: +1 HP per second after invincibility ends.
- Enemy shoot cooldown scales with level (80 frames early → 40 frames late).
- ~20 hits needed to die (10 HP + sustained regen).

v6.4:
- FIX: Exit bug — levels without keys were blocked by quest check (dead loop).
- FIX: Locked exit always blocked even after quest completion — now passes when all_done.
- FIX: Missing WALL_SAND/DIRT/LOG in blocking() — player could walk through sand/dirt/log.
- Minecraft mode: pure flatland (no walls, no random blocks, open sky).
- Day/night cycle: sun/moon arc across sky, brightness changes, stars at night.
- MC controls: OK short=place, OK long=mine, Back short=switch block.
- MC HUD: 8-slot hotbar with icons, MC-style heart health bar (10 hearts).

v6.3:
- Minecraft texture pack: 12 MC-style textures (grass side, dirt, log, leaves, sand, etc.).
- New blocks: WALL_SAND, WALL_DIRT, WALL_LOG (3 new block types).
- Water animation: wave texture scrolls with game tick.
- MC sky: gradient ceiling + 5×5 sun with cross rays.
- Sand landing particles: dust burst when placing sand/dirt.
- MC survival: mine block → auto-switch held to that block type.
- 8 placeable blocks: Brick/Stone/Wood/Grass/Dirt/Sand/Log/Leaf.

v6.2:
- Input redefinition: OK short=shoot (all modes), OK long=mine (MC mode).
- Back short=place block (MC mode), Back long=exit.
- Contrast crosshair: XOR rendering ensures visibility on any background.
- Particle system: 32-particle pool (shooting sparks, hit explosions, bullet trails, walking dust).
- Global brightness boost + enemy movement frequency increased.

v6.0:
- Combat system: shooting with bullets, enemy AI (chase + ranged).
- Quest/task system: FIND_EXIT, GET_KEY, OPEN_DOOR, KILL_ENEMY, SURVIVE.
- Achievement system: total kills, total clears, total mined, milestone flags.
- Story mode: prologue with branching choices (Warrior +HP / Seeker +torch).
- Level stages: 1-10 maze, 11-20 puzzle, 21-50 combat.
- Locked exits: quest-gated exits that unlock on task completion.
- New items: potions, amulets, traps, ammo pickups.

v4.4.1:
- Opening animation plays to completion (~4.5s, full BGM).
- Developer mode unlock sequence via long-press during opening.

v4.4:
- Developer mode: unlocks all campaign levels, debug overlay.
- Settings rewrite: centered options, scrollable list.

v4.3.1:
- FIX: no sound — speaker was never acquired.

v4.3:
- Opening animation: 4-stage intro with BGM.
- SFX system: tick-based sequencer, no external audio files.
- Settings screen: SFX and Opening toggles.

v4.2:
- Quest/task system for story levels.
- Enemy combat: enemies have HP, dashing deals damage.

v4.1:
- FIX: Endless Mode crash — stack overflow from large local arrays.

v4.0:
- Endless Mode stability: size cap, DDA step cap, seed hashing.
- Smooth controls: fractional step interpolation.
- Big exit marker + 3D sprites for ground items.

v3.3:
- Level select rewrite: scrollable list.
- In-game HUD + Map Panel with minimap.

v3.2:
- Full Chinese localization (XBM bitmaps).

v3.0:
- Endless mode level select.
- Inventory system: Potion, Amulet.
- Story mode with branching choices.

v2.1:
- Bilingual UI: Chinese / English switch.

v2.0:
- Half-resolution raycasting (64 columns).
- On-demand world tick (~8 Hz).
- Compass, minimap, exit highlight.

v1.0:
- Initial release: Campaign + Endless + Visitor modes.
- Recursive-backtracker maze generation.
- Items, enemy AI, NPC visitors.
- 4 wall textures with distance & orientation shading.
