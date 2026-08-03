v4.4:
- Developer mode: unlocks all campaign levels from the level-select screen and enables a debug overlay. Persists across sessions.
- Debug overlay: top status bar over the 3D view showing level/floor, player X/Y, world tick, actor count, facing direction. Toggled from Settings (visible once developer mode is active).
- Settings rewrite: option rows horizontally centered; scrollable list with ^/v indicators; bottom hint bar no longer overlaps the last option. Up/Down now move the cursor in opposite directions.
- Save format stays MAZ4 (new flags reuse reserved bytes; old v4.3 saves load with defaults).

v4.3.1:
- FIX: no sound — speaker was never acquired, so every SFX was silently dropped. sfx_init() now acquires the speaker; all SFX and the opening BGM play correctly.

v4.3:
- Opening animation on app start: 4-stage intro (logo drop + bounce, particle burst, subtitle slide-up, blinking prompt) with a C-major chiptune BGM. Any key skips to the menu. Can be disabled from Settings (persisted).
- SFX using the Flipper speaker: menu move/confirm, pickup, door, trap, damage, attack, kill, quest/level clear, game over, story page turn. Tick-based sequencer, no external audio files.
- New Settings screen: SFX and Opening toggles, persisted (MAZ4; old MAZ3 saves migrated).

v4.2:
- Quest/task system for story levels: long-press OK pauses and opens a 2-page Inventory (items + quest). Press Left/Right to switch pages.
- Quests on story levels: Level 1 (Find Exit), puzzle levels 10–19 (Get Key + Open Door), combat levels 20+ (Kill all enemies). Completing all subtasks grants a one-time full-HP reward.
- Enemy combat: enemies have HP (2). Dashing (OK) into an enemy in front deals 1 damage; two dashes kill it.

v4.1:
- FIX: Endless Mode crash — maze-carving DFS used two 3844-byte local arrays that overflowed the 8 KB stack. Moved to static storage; stack raised to 12 KB.

v4.0:
- Endless Mode stability: tight maze size cap, DDA step cap, render guard, better seed hashing.
- Smooth controls: direction keys set target rotation/move; game_update applies a fractional step each frame.
- Big exit marker: a down-arrow at the top showing the exit direction; a blinking frame when the exit is straight ahead.
- 3D sprites for ground items (key/torch/potion/amulet/trap/exit) with depth scaling.

v3.3:
- Level select rewrite: smaller font, scrollable list (7 rows) with ^/v indicators.
- In-game HUD hidden by default; long-press OK opens a full Map Panel (HUD bar + minimap + exit arrow).
- Inventory shows a compact HUD status bar at the top.

v3.2:
- Full Chinese localization of story, inventory, and level-select screens (XBM bitmaps).

v3.1:
- Force full rebuild so the published fap actually contains the v3.0 features.

v3.0:
- Endless mode lets you pick any level to enter (level select).
- Inventory: long-press OK in game; Up/Down select, OK use, Back resume.
- New items: Potion (restore HP), Amulet (warp to start).
- Story mode: 600-word prologue with 2 branching choices (Warrior +HP / Seeker +torch).
- Level select before Story mode: cleared replayable, uncleared locked.

v2.1:
- Bilingual UI: switch Chinese / English from the menu (Left / Right).

v2.0:
- Half-resolution raycasting (64 columns) for stable performance.
- On-demand world tick (~8 Hz) to prevent flicker/crash.
- Compass to exit, minimap, exit highlight.
- Chinese XBM bitmaps for all in-game text.

v1.0:
- Initial release: Campaign + Endless + Visitor modes.
- Recursive-backtracker maze generation, difficulty scaling.
- Items (key/torch/trap/door), enemy AI, NPC visitors.
- 4 wall textures with distance & orientation shading.
