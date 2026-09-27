#include <furi.h>
#include <gui/gui.h>
#include <gui/view_port.h>
#include <input/input.h>
#include <notification/notification_messages.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define FRAME_MS        25U
#define EXIT_FLAG       (1U << 0)
#define PIPE_COUNT      3U
#define PIPE_WIDTH      12
#define PIPE_SPACING    64
#define GAP_HEIGHT      32
#define PIPE_MIN_HEIGHT 8
#define BIRD_X          26
#define BIRD_WIDTH      7
#define BIRD_HEIGHT     6
#define FLOOR_Y         63

typedef enum {
    GameReady,
    GamePlaying,
    GameOver,
} GamePhase;

typedef struct {
    float x;
    int gap_top;
    bool scored;
} Pipe;

typedef struct {
    float bird_y;
    float velocity;
    Pipe pipes[PIPE_COUNT];
    uint32_t score;
    uint32_t random_state;
    GamePhase phase;
} Game;

typedef struct {
    Game game;
    FuriMutex* mutex;
    FuriMessageQueue* input_queue;
    FuriThreadId thread_id;
} FlappyBirdApp;

static int random_gap(Game* game) {
    uint32_t value = game->random_state;
    value ^= value << 13;
    value ^= value >> 17;
    value ^= value << 5;
    game->random_state = value;
    /* Keep both pipes visible even with the more forgiving gap. */
    return PIPE_MIN_HEIGHT + (int)(value % (FLOOR_Y - GAP_HEIGHT - 2 * PIPE_MIN_HEIGHT + 1));
}

static void game_reset(Game* game) {
    game->bird_y = 29.0f;
    game->velocity = 0.0f;
    game->score = 0;
    game->phase = GamePlaying;
    for(size_t i = 0; i < PIPE_COUNT; ++i) {
        game->pipes[i].x = 128.0f + (float)(i * PIPE_SPACING);
        game->pipes[i].gap_top = random_gap(game);
        game->pipes[i].scored = false;
    }
}

/* Called only by the app thread, with the model mutex held. */
static bool game_step(Game* game) {
    if(game->phase != GamePlaying) return false;

    game->velocity += 0.14f;
    if(game->velocity > 2.4f) game->velocity = 2.4f;
    game->bird_y += game->velocity;

    bool hit = game->bird_y <= 0.0f || game->bird_y + BIRD_HEIGHT >= FLOOR_Y;
    for(size_t i = 0; i < PIPE_COUNT; ++i) {
        game->pipes[i].x -= 0.85f;
    }
    for(size_t i = 0; i < PIPE_COUNT; ++i) {
        Pipe* pipe = &game->pipes[i];
        if(pipe->x + PIPE_WIDTH <= 0.0f) {
            float rightmost = pipe->x;
            for(size_t j = 0; j < PIPE_COUNT; ++j) {
                if(game->pipes[j].x > rightmost) rightmost = game->pipes[j].x;
            }
            pipe->x = rightmost + PIPE_SPACING;
            pipe->gap_top = random_gap(game);
            pipe->scored = false;
        }

        const bool overlap = BIRD_X + BIRD_WIDTH > pipe->x && BIRD_X < pipe->x + PIPE_WIDTH;
        if(overlap && (game->bird_y < pipe->gap_top ||
                       game->bird_y + BIRD_HEIGHT > pipe->gap_top + GAP_HEIGHT)) {
            hit = true;
        }
    }

    if(hit) {
        game->phase = GameOver;
        return true;
    }

    for(size_t i = 0; i < PIPE_COUNT; ++i) {
        Pipe* pipe = &game->pipes[i];
        if(!pipe->scored && pipe->x + PIPE_WIDTH < BIRD_X) {
            pipe->scored = true;
            if(game->score < UINT32_MAX) ++game->score;
        }
    }
    return false;
}

static void draw_callback(Canvas* canvas, void* context) {
    FlappyBirdApp* app = context;
    /* Copy briefly under the lock; never hold it while calling GUI functions. */
    furi_mutex_acquire(app->mutex, FuriWaitForever);
    const Game game = app->game;
    furi_mutex_release(app->mutex);

    canvas_clear(canvas);
    canvas_set_color(canvas, ColorBlack);
    for(size_t i = 0; i < PIPE_COUNT; ++i) {
        const Pipe* pipe = &game.pipes[i];
        const int x = (int)pipe->x;
        if(x >= 128 || x + PIPE_WIDTH <= 0) continue;
        const int left = x < 0 ? 0 : x;
        const int right = x + PIPE_WIDTH > 128 ? 128 : x + PIPE_WIDTH;
        const int bottom = pipe->gap_top + GAP_HEIGHT;
        canvas_draw_box(canvas, left, 0, right - left, pipe->gap_top);
        canvas_draw_box(canvas, left, bottom, right - left, FLOOR_Y - bottom);
    }
    canvas_draw_line(canvas, 0, FLOOR_Y, 127, FLOOR_Y);

    int y = (int)game.bird_y;
    if(y < 1) y = 1;
    if(y > FLOOR_Y - BIRD_HEIGHT) y = FLOOR_Y - BIRD_HEIGHT;
    canvas_draw_box(canvas, BIRD_X, y + 1, 6, 4);
    canvas_draw_line(canvas, BIRD_X + 2, y, BIRD_X + 4, y);
    canvas_draw_line(canvas, BIRD_X + 1, y + 5, BIRD_X + 4, y + 5);
    canvas_draw_dot(canvas, BIRD_X + 6, y + 3);
    canvas_set_color(canvas, ColorWhite);
    canvas_draw_dot(canvas, BIRD_X + 4, y + 1);
    canvas_set_color(canvas, ColorBlack);

    char score[32];
    snprintf(score, sizeof(score), "Score: %lu", (unsigned long)game.score);
    canvas_set_font(canvas, FontSecondary);
    if(game.phase == GamePlaying) {
        canvas_set_color(canvas, ColorWhite);
        canvas_draw_box(canvas, 0, 0, canvas_string_width(canvas, score) + 4, 11);
        canvas_set_color(canvas, ColorBlack);
        canvas_draw_str(canvas, 2, 8, score);
    } else {
        canvas_set_color(canvas, ColorWhite);
        canvas_draw_box(canvas, 8, 8, 112, 48);
        canvas_set_color(canvas, ColorBlack);
        canvas_draw_frame(canvas, 8, 8, 112, 48);
        canvas_set_font(canvas, FontPrimary);
        canvas_draw_str_aligned(
            canvas,
            64,
            19,
            AlignCenter,
            AlignCenter,
            game.phase == GameOver ? "Game Over" : "Flappy Bird");
        canvas_set_font(canvas, FontSecondary);
        canvas_draw_str_aligned(
            canvas,
            64,
            31,
            AlignCenter,
            AlignCenter,
            game.phase == GameOver ? score : "Fly through the gaps!");
        canvas_draw_str_aligned(
            canvas,
            64,
            42,
            AlignCenter,
            AlignCenter,
            game.phase == GameOver ? "OK: restart" : "OK: start / flap");
        canvas_draw_str_aligned(canvas, 64, 51, AlignCenter, AlignCenter, "BACK: exit");
    }
}

static void input_callback(InputEvent* event, void* context) {
    FlappyBirdApp* app = context;
    if(event->key == InputKeyBack && event->type == InputTypePress) {
        /* Exit cannot be lost when the input queue is full. Never block GUI input. */
        furi_thread_flags_set(app->thread_id, EXIT_FLAG);
    } else if(event->key == InputKeyOk && event->type == InputTypeShort) {
        furi_message_queue_put(app->input_queue, event, 0);
    }
}

int32_t flappy_bird_app(void* context) {
    UNUSED(context);
    FlappyBirdApp* app = malloc(sizeof(FlappyBirdApp));
    app->mutex = furi_mutex_alloc(FuriMutexTypeNormal);
    app->input_queue = furi_message_queue_alloc(8, sizeof(InputEvent));
    app->thread_id = furi_thread_get_current_id();
    app->game = (Game){.random_state = furi_get_tick() | 1U};
    game_reset(&app->game);
    app->game.phase = GameReady;
    furi_thread_flags_clear(EXIT_FLAG);

    Gui* gui = furi_record_open(RECORD_GUI);
    NotificationApp* notifications = furi_record_open(RECORD_NOTIFICATION);
    ViewPort* view_port = view_port_alloc();
    view_port_draw_callback_set(view_port, draw_callback, app);
    view_port_input_callback_set(view_port, input_callback, app);
    gui_add_view_port(gui, view_port, GuiLayerFullscreen);

    const uint32_t frame_ticks = furi_ms_to_ticks(FRAME_MS);
    uint32_t last_frame = furi_get_tick();
    while(!(furi_thread_flags_get() & EXIT_FLAG)) {
        const uint32_t elapsed = furi_get_tick() - last_frame;
        const uint32_t wait = elapsed < frame_ticks ? frame_ticks - elapsed : 0;
        InputEvent event;
        const bool received = furi_message_queue_get(app->input_queue, &event, wait) ==
                              FuriStatusOk;
        if(furi_thread_flags_get() & EXIT_FLAG) break;

        bool hit = false;
        bool changed = false;
        furi_mutex_acquire(app->mutex, FuriWaitForever);
        if(received) {
            if(app->game.phase != GamePlaying) {
                game_reset(&app->game);
                last_frame = furi_get_tick();
            }
            app->game.velocity = -1.75f;
            changed = true;
        }

        /* Fixed 40 Hz simulation; cap catch-up work after a scheduling stall. */
        const uint32_t now = furi_get_tick();
        uint32_t steps = (now - last_frame) / frame_ticks;
        if(steps > 4) {
            steps = 4;
            last_frame = now - steps * frame_ticks;
        }
        while(steps-- > 0) {
            hit |= game_step(&app->game);
            last_frame += frame_ticks;
            changed = true;
        }
        furi_mutex_release(app->mutex);

        if(hit) notification_message(notifications, &sequence_single_vibro);
        if(changed) view_port_update(view_port);
    }

    /* Detach and synchronize GUI callbacks before freeing their context. */
    view_port_enabled_set(view_port, false);
    gui_remove_view_port(gui, view_port);
    view_port_free(view_port);
    notification_message_block(notifications, &sequence_reset_vibro);
    furi_record_close(RECORD_NOTIFICATION);
    furi_record_close(RECORD_GUI);
    furi_message_queue_free(app->input_queue);
    furi_mutex_free(app->mutex);
    furi_thread_flags_clear(EXIT_FLAG);
    free(app);
    return 0;
}
