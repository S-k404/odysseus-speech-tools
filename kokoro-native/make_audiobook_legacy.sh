#!/usr/bin/env bash
# =============================================================================
# make_audiobook.sh — Drop-in audiobook factory with Kokoro Apple Metal GPU
#
# Usage:
#   make_audiobook [options] [target ...] [voice]
#
# Examples:
#   make_audiobook 1                            # Interactive voice selector menu
#   make_audiobook 1 bella                      # Voice tag at the end (Bella)
#   make_audiobook 1 adam                       # Voice tag at the end (Adam)
#   make_audiobook 10 george                    # Voice tag at the end (George)
#   make_audiobook "GATE" emma                  # Voice tag on title query
#   make_audiobook mybook.pdf adam              # Voice tag on file path
#   make_audiobook 1:bella                      # Colon notation tag
#   make_audiobook -v af_bella 1                # Standard flag
#   make_audiobook --voices                     # View voice guide & samples
#   make_audiobook --list                       # List books in ~/Documents/Books
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
KOKORO_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
BOOKS_DIR="${BOOKS_DIR:-$HOME/Documents/Books}"
AUDIO_DIR="${AUDIO_DIR:-$HOME/Documents/AudioBook}"
CONVERTER="$HOME/Documents/Docker/Speaches/pdf2epub_tts.py"
KOKORO_VENV="$KOKORO_DIR/.venv"
PYTHON="$KOKORO_VENV/bin/python"
KOKORO_PORT=8001
KOKORO_ENDPOINT="http://localhost:$KOKORO_PORT/v1"

# TTS settings (defaults, can be overridden by flags, trailing tag, or env)
DEFAULT_VOICE="af_heart"
VOICE="${VOICE:-$DEFAULT_VOICE}"
VOICE_EXPLICITLY_SET=false
if [[ -n "${VOICE_ENV:-}" || "${VOICE}" != "$DEFAULT_VOICE" ]]; then
    VOICE_EXPLICITLY_SET=true
fi
SPEED="${SPEED:-1.0}"
CONCURRENCY="${CONCURRENCY:-4}"
AUDIO_FORMAT="${AUDIO_FORMAT:-m4b}"   # m4b (with chapters) or mp3
PROMPT_VOICE=true
DRY_RUN=false

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'; MAGENTA=$'\033[0;35m'; BOLD=$'\033[1m'; RESET=$'\033[0m'

info()    { echo -e "${CYAN}ℹ️  $*${RESET}"; }
success() { echo -e "${GREEN}✅  $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠️  $*${RESET}"; }
error()   { echo -e "${RED}❌  $*${RESET}" >&2; }
header()  { echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════════════════════${RESET}"; \
             echo -e "${BOLD}${CYAN}  $*${RESET}"; \
             echo -e "${BOLD}${CYAN}══════════════════════════════════════════════════════════${RESET}"; }

# ---------------------------------------------------------------------------
# Voice Utilities
# ---------------------------------------------------------------------------
resolve_voice_alias() {
    local v
    v="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
    case "$v" in
        heart)    echo "af_heart" ;;
        bella)    echo "af_bella" ;;
        sky)      echo "af_sky" ;;
        nicole)   echo "af_nicole" ;;
        sarah)    echo "af_sarah" ;;
        alloy)    echo "af_alloy" ;;
        aoede)    echo "af_aoede" ;;
        jessica)  echo "af_jessica" ;;
        river)    echo "af_river" ;;
        kore)     echo "af_kore" ;;
        adam)     echo "am_adam" ;;
        michael)  echo "am_michael" ;;
        echo)     echo "am_echo" ;;
        eric)     echo "am_eric" ;;
        fenrir)   echo "am_fenrir" ;;
        liam)     echo "am_liam" ;;
        onyx)     echo "am_onyx" ;;
        puck)     echo "am_puck" ;;
        santa)    echo "am_santa" ;;
        emma)     echo "bf_emma" ;;
        alice)    echo "bf_alice" ;;
        isabella) echo "bf_isabella" ;;
        lily)     echo "bf_lily" ;;
        george)   echo "bm_george" ;;
        daniel)   echo "bm_daniel" ;;
        fable)    echo "bm_fable" ;;
        lewis)    echo "bm_lewis" ;;
        *)        echo "$v" ;;
    esac
}

is_known_voice() {
    local v
    v="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
    case "$v" in
        af_heart|heart|af_bella|bella|af_sky|sky|af_nicole|nicole|af_sarah|sarah|\
        af_alloy|alloy|af_aoede|aoede|af_jessica|jessica|af_river|river|af_kore|kore|\
        am_adam|adam|am_michael|michael|am_echo|echo|am_eric|eric|am_fenrir|fenrir|\
        am_liam|liam|am_onyx|onyx|am_puck|puck|am_santa|santa|\
        bf_emma|emma|bf_alice|alice|bf_isabella|isabella|bf_lily|lily|\
        bm_george|george|bm_daniel|daniel|bm_fable|fable|bm_lewis|lewis|\
        af_*|am_*|bf_*|bm_*|zf_*|zm_*|ef_*|em_*|ff_*|hf_*|hm_*|if_*|im_*|jf_*|jm_*|pf_*|pm_*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

select_voice_interactive() {
    # If not connected to interactive terminal, keep current voice
    if [[ ! -t 0 ]]; then
        return
    fi

    echo ""
    echo -e "${BOLD}${CYAN}🎙️  Select a Voice for this Audiobook:${RESET}"
    echo -e "  ${BOLD}${GREEN}1)${RESET} ${BOLD}af_heart${RESET}   (alias: ${CYAN}heart${RESET})   — ★ American Female (Warm, expressive, highest quality) [Default]"
    echo -e "  ${BOLD}${GREEN}2)${RESET} ${BOLD}af_bella${RESET}   (alias: ${CYAN}bella${RESET})   — American Female (Gentle, storytelling, fiction)"
    echo -e "  ${BOLD}${GREEN}3)${RESET} ${BOLD}af_sky${RESET}     (alias: ${CYAN}sky${RESET})     — American Female (Bright, upbeat, clear)"
    echo -e "  ${BOLD}${GREEN}4)${RESET} ${BOLD}am_adam${RESET}    (alias: ${CYAN}adam${RESET})    — American Male (Deep, resonant, authoritative narrator)"
    echo -e "  ${BOLD}${GREEN}5)${RESET} ${BOLD}am_michael${RESET} (alias: ${CYAN}michael${RESET}) — American Male (Warm, conversational podcast style)"
    echo -e "  ${BOLD}${GREEN}6)${RESET} ${BOLD}am_onyx${RESET}    (alias: ${CYAN}onyx${RESET})    — American Male (Cinematic baritone, deep)"
    echo -e "  ${BOLD}${GREEN}7)${RESET} ${BOLD}bf_emma${RESET}    (alias: ${CYAN}emma${RESET})    — British Female (Classic British RP, articulate, polished)"
    echo -e "  ${BOLD}${GREEN}8)${RESET} ${BOLD}bm_george${RESET}  (alias: ${CYAN}george${RESET})  — British Male (Distinguished literature narrator)"
    echo -e "  ${BOLD}${GREEN}9)${RESET} ${MAGENTA}Custom / Other...${RESET}          (Type any Kokoro voice name or alias)"
    echo ""
    read -r -p "👉 Choose voice [1-9, name, or Press Enter for default]: " choice
    choice="$(echo "$choice" | tr -d '[:space:]')"

    case "$choice" in
        ""|1) VOICE="af_heart" ;;
        2)    VOICE="af_bella" ;;
        3)    VOICE="af_sky" ;;
        4)    VOICE="am_adam" ;;
        5)    VOICE="am_michael" ;;
        6)    VOICE="am_onyx" ;;
        7)    VOICE="bf_emma" ;;
        8)    VOICE="bm_george" ;;
        9)
            read -r -p "Enter voice code or alias (e.g. af_sarah, daniel, nicole): " custom_v
            custom_v="$(echo "$custom_v" | tr -d '[:space:]')"
            if [[ -n "$custom_v" ]]; then
                VOICE="$(resolve_voice_alias "$custom_v")"
            else
                VOICE="af_heart"
            fi
            ;;
        *)
            # The user might have typed a voice name directly like "adam" or "bella"
            VOICE="$(resolve_voice_alias "$choice")"
            ;;
    esac
    VOICE_EXPLICITLY_SET=true
    echo -e "✅ Selected voice: ${BOLD}${GREEN}$VOICE${RESET}\n"
}

# ---------------------------------------------------------------------------
# Help & Voices Guide
# ---------------------------------------------------------------------------
show_help() {
    cat << EOF
${BOLD}${CYAN}📚 Audiobook Factory — Kokoro Apple Metal GPU${RESET}

${BOLD}Usage:${RESET}
  make_audiobook [options] [target ...] [voice_tag]

${BOLD}Quick Run with Voice Tag at the End:${RESET}
  make_audiobook 1 bella                      # Convert book #1 using Bella
  make_audiobook 1 adam                       # Convert book #1 using Adam
  make_audiobook 10 george                    # Convert book #10 using George (British)
  make_audiobook "GATE" emma                  # Convert GATE using Emma (British)
  make_audiobook mybook.pdf onyx              # Convert PDF using deep baritone Onyx
  make_audiobook 1:bella                      # Colon syntax also supported

${BOLD}Interactive Selection:${RESET}
  make_audiobook 1                            # Interactive numbered menu to pick voice
  make_audiobook                              # Batch mode with interactive menu

${BOLD}Options:${RESET}
  ${GREEN}-v, --voice <voice>${RESET}      Select voice explicitly (e.g. -v bella or -v am_adam)
  ${GREEN}--voices${RESET}                 Display full Kokoro voice guide and style descriptions
  ${GREEN}-s, --speed <speed>${RESET}      Speech playback speed (e.g. 1.0, 1.15, 1.25) (default: $SPEED)
  ${GREEN}-f, --format <fmt>${RESET}       Output audio format: ${BOLD}m4b${RESET} (with chapters) or ${BOLD}mp3${RESET} (default: $AUDIO_FORMAT)
  ${GREEN}-c, --concurrency <n>${RESET}    Parallel chapter workers (default: $CONCURRENCY)
  ${GREEN}--no-prompt${RESET}              Skip interactive voice prompt, use default/current voice
  ${GREEN}-l, --list${RESET}               List available books in ~/Documents/Books
  ${GREEN}-h, --help${RESET}               Show this help message

${BOLD}Available Voice Aliases for Tagging:${RESET}
  Female: ${CYAN}heart${RESET}, ${CYAN}bella${RESET}, ${CYAN}sky${RESET}, ${CYAN}nicole${RESET}, ${CYAN}sarah${RESET}, ${CYAN}river${RESET}, ${CYAN}emma${RESET}, ${CYAN}alice${RESET}, ${CYAN}isabella${RESET}, ${CYAN}lily${RESET}
  Male:   ${CYAN}adam${RESET}, ${CYAN}michael${RESET}, ${CYAN}onyx${RESET}, ${CYAN}echo${RESET}, ${CYAN}eric${RESET}, ${CYAN}liam${RESET}, ${CYAN}george${RESET}, ${CYAN}daniel${RESET}, ${CYAN}fable${RESET}, ${CYAN}lewis${RESET}
EOF
}

show_voices() {
    cat << EOF
${BOLD}${CYAN}🎙️ Available Kokoro Voices (Apple Silicon GPU Accelerated):${RESET}

  ${BOLD}${MAGENTA}American Female (af_*):${RESET}
    ${GREEN}af_heart${RESET}     (alias: ${CYAN}heart${RESET})    ★ ${BOLD}DEFAULT${RESET}: Warm, expressive, highest quality
    ${GREEN}af_bella${RESET}     (alias: ${CYAN}bella${RESET})    Gentle, melodic, ideal for fiction & storytelling
    ${GREEN}af_sky${RESET}       (alias: ${CYAN}sky${RESET})      Bright, clear, upbeat, energetic
    ${GREEN}af_nicole${RESET}    (alias: ${CYAN}nicole${RESET})   Crisp, conversational, modern
    ${GREEN}af_sarah${RESET}     (alias: ${CYAN}sarah${RESET})    Professional, balanced, great for non-fiction
    ${GREEN}af_river${RESET}     (alias: ${CYAN}river${RESET})    Soft, calm, relaxed cadence
    ${GREEN}af_alloy${RESET}     (alias: ${CYAN}alloy${RESET})    Direct, clear, modern technical
    ${GREEN}af_aoede${RESET}     (alias: ${CYAN}aoede${RESET})    Melodic, lyrical
    ${GREEN}af_jessica${RESET}   (alias: ${CYAN}jessica${RESET})  Articulate, corporate, authoritative

  ${BOLD}${MAGENTA}American Male (am_*):${RESET}
    ${GREEN}am_adam${RESET}      (alias: ${CYAN}adam${RESET})     Deep, steady, resonant, authoritative narrator
    ${GREEN}am_michael${RESET}   (alias: ${CYAN}michael${RESET})  Warm, friendly, engaging podcast style
    ${GREEN}am_onyx${RESET}      (alias: ${CYAN}onyx${RESET})     Cinematic, deep baritone
    ${GREEN}am_echo${RESET}      (alias: ${CYAN}echo${RESET})     Bright, crisp, clear
    ${GREEN}am_eric${RESET}      (alias: ${CYAN}eric${RESET})     Dynamic, enthusiastic
    ${GREEN}am_fenrir${RESET}    (alias: ${CYAN}fenrir${RESET})   Gravelly, deep, narrative
    ${GREEN}am_liam${RESET}      (alias: ${CYAN}liam${RESET})     Young, casual, natural
    ${GREEN}am_puck${RESET}      (alias: ${CYAN}puck${RESET})     Spirited, playful, expressive

  ${BOLD}${MAGENTA}British Female (bf_*):${RESET}
    ${GREEN}bf_emma${RESET}      (alias: ${CYAN}emma${RESET})     Classic British RP, articulate, polished narrator
    ${GREEN}bf_alice${RESET}     (alias: ${CYAN}alice${RESET})    Crisp, intellectual, precise
    ${GREEN}bf_isabella${RESET}  (alias: ${CYAN}isabella${RESET}) Elegant British, gentle
    ${GREEN}bf_lily${RESET}      (alias: ${CYAN}lily${RESET})     Warm, inviting, gentle

  ${BOLD}${MAGENTA}British Male (bm_*):${RESET}
    ${GREEN}bm_george${RESET}    (alias: ${CYAN}george${RESET})   Distinguished British narrator, classic audiobook style
    ${GREEN}bm_daniel${RESET}    (alias: ${CYAN}daniel${RESET})   Calm, thoughtful, measured
    ${GREEN}bm_fable${RESET}     (alias: ${CYAN}fable${RESET})    Storyteller, theatrical cadence
    ${GREEN}bm_lewis${RESET}     (alias: ${CYAN}lewis${RESET})    Contemporary British, youthful

${BOLD}Quick Run Examples with Tag at End:${RESET}
  make_audiobook 1 bella
  make_audiobook 10 george
  make_audiobook "Python" adam
EOF
}

# ---------------------------------------------------------------------------
# Argument Parsing
# ---------------------------------------------------------------------------
RAW_TARGETS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--voice)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                VOICE="$(resolve_voice_alias "$2")"
                VOICE_EXPLICITLY_SET=true
                PROMPT_VOICE=false
                shift 2
            else
                error "Missing argument for --voice (e.g. -v af_heart or -v bella)"
                exit 1
            fi
            ;;
        --voices)
            show_voices
            exit 0
            ;;
        -s|--speed)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                SPEED="$2"
                shift 2
            else
                error "Missing argument for --speed (e.g. -s 1.15)"
                exit 1
            fi
            ;;
        -f|--format)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                AUDIO_FORMAT="$2"
                shift 2
            else
                error "Missing argument for --format (e.g. -f m4b or -f mp3)"
                exit 1
            fi
            ;;
        -c|--concurrency)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                CONCURRENCY="$2"
                shift 2
            else
                error "Missing argument for --concurrency (e.g. -c 4)"
                exit 1
            fi
            ;;
        -n|--dry-run)
            DRY_RUN=true
            PROMPT_VOICE=false
            shift
            ;;
        --no-prompt)
            PROMPT_VOICE=false
            shift
            ;;
        -l|--list)
            "$PYTHON" "$CONVERTER" --books-dir "$BOOKS_DIR" --audio-dir "$AUDIO_DIR" --list
            exit 0
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                RAW_TARGETS+=("$1")
                shift
            done
            break
            ;;
        -*)
            error "Unknown option: $1"
            echo "Run 'make_audiobook --help' for usage."
            exit 1
            ;;
        *)
            RAW_TARGETS+=("$1")
            shift
            ;;
    esac
done

# Pre-checks
if [[ ! -f "$CONVERTER" ]]; then
    error "Converter not found: $CONVERTER"
    exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
    error "Venv python not found at $PYTHON. Run $KOKORO_DIR/start.sh --setup first."
    exit 1
fi

# ---------------------------------------------------------------------------
# Check for Trailing Voice Tag or Colon Tag
# ---------------------------------------------------------------------------
FINAL_TARGETS=()

if [[ ${#RAW_TARGETS[@]} -ge 2 ]]; then
    # Check if last argument is a known voice tag
    last_idx=$(( ${#RAW_TARGETS[@]} - 1 ))
    candidate="${RAW_TARGETS[$last_idx]}"
    if is_known_voice "$candidate"; then
        VOICE="$(resolve_voice_alias "$candidate")"
        VOICE_EXPLICITLY_SET=true
        PROMPT_VOICE=false
        # Remove the voice tag from targets
        for (( i=0; i<last_idx; i++ )); do
            FINAL_TARGETS+=("${RAW_TARGETS[$i]}")
        done
    else
        FINAL_TARGETS=("${RAW_TARGETS[@]}")
    fi
elif [[ ${#RAW_TARGETS[@]} -eq 1 ]]; then
    item="${RAW_TARGETS[0]}"
    # Check if sole argument is a known voice tag (e.g. make_audiobook adam) -> batch with that voice
    if is_known_voice "$item"; then
        VOICE="$(resolve_voice_alias "$item")"
        VOICE_EXPLICITLY_SET=true
        PROMPT_VOICE=false
        FINAL_TARGETS=()
    # Check if argument contains colon (e.g. make_audiobook 1:bella or mybook.pdf:adam)
    elif [[ "$item" == *:* ]] && is_known_voice "${item##*:}"; then
        VOICE="$(resolve_voice_alias "${item##*:}")"
        VOICE_EXPLICITLY_SET=true
        PROMPT_VOICE=false
        FINAL_TARGETS+=("${item%%:*}")
    else
        FINAL_TARGETS+=("$item")
    fi
else
    FINAL_TARGETS=()
fi

# If single directory argument passed in targets, treat as BOOKS_DIR
if [[ ${#FINAL_TARGETS[@]} -eq 1 && -d "${FINAL_TARGETS[0]}" ]]; then
    BOOKS_DIR="$(cd "${FINAL_TARGETS[0]}" && pwd)"
    FINAL_TARGETS=()
fi

mkdir -p "$BOOKS_DIR" "$AUDIO_DIR"

# ---------------------------------------------------------------------------
# Interactive Voice Selection (if not specified by flag or tag)
# ---------------------------------------------------------------------------
if [[ "$VOICE_EXPLICITLY_SET" == false && "$PROMPT_VOICE" == true ]]; then
    select_voice_interactive
fi

VOICE="$(resolve_voice_alias "$VOICE")"

if [[ "$DRY_RUN" == true ]]; then
    header "🔍 Dry Run — Audiobook Factory"
    info "Target(s):    ${FINAL_TARGETS[*]:-(Batch all pending in $BOOKS_DIR)}"
    info "Voice:        ${BOLD}${GREEN}$VOICE${RESET}"
    info "Speed:        ${SPEED}x"
    info "Audio format: $AUDIO_FORMAT"
    info "Workers:      $CONCURRENCY"
    exit 0
fi

# ---------------------------------------------------------------------------
# On-demand Kokoro GPU server lifecycle
# ---------------------------------------------------------------------------
WE_STARTED_SERVER=false

stop_kokoro_server() {
    if [[ "$WE_STARTED_SERVER" == true ]]; then
        echo ""
        info "Stopping Kokoro GPU server (on-demand mode)..."
        if [[ -f "$KOKORO_DIR/server.pid" ]]; then
            local pid
            pid="$(cat "$KOKORO_DIR/server.pid" 2>/dev/null || true)"
            if [[ -n "$pid" ]]; then
                kill "$pid" 2>/dev/null || true
            fi
            rm -f "$KOKORO_DIR/server.pid"
        fi
        pkill -f "uvicorn server:app.*8001" 2>/dev/null || true
        success "Kokoro GPU server stopped"
    fi
}

trap stop_kokoro_server EXIT

start_kokoro_server() {
    if curl -sf "http://localhost:$KOKORO_PORT/health" >/dev/null 2>&1; then
        success "Kokoro GPU server already running on port $KOKORO_PORT (will leave running)"
        return
    fi

    info "Starting Kokoro GPU server on port $KOKORO_PORT..."
    source "$KOKORO_VENV/bin/activate"
    nohup uvicorn server:app --app-dir "$KOKORO_DIR" \
        --host 0.0.0.0 --port "$KOKORO_PORT" --workers 1 \
        > "$KOKORO_DIR/server.log" 2>&1 &
    local server_pid=$!
    echo "$server_pid" > "$KOKORO_DIR/server.pid"
    WE_STARTED_SERVER=true

    # Wait up to 30s for the server to be ready
    local waited=0
    while ! curl -sf "http://localhost:$KOKORO_PORT/health" >/dev/null 2>&1; do
        sleep 2; waited=$((waited + 2))
        if [[ $waited -ge 30 ]]; then
            error "Server failed to start. Check $KOKORO_DIR/server.log"
            exit 1
        fi
        echo -n "."
    done
    echo ""
    success "Kokoro GPU server ready (PID $server_pid)"

    # Confirm Metal GPU
    local dev_check
    dev_check=$("$PYTHON" -c \
        "import torch; print('MPS' if torch.backends.mps.is_available() else 'CPU')" 2>/dev/null || echo "CPU")
    if [[ "$dev_check" == "MPS" ]]; then
        success "Apple Metal GPU (MPS) is ACTIVE — 100% GPU inference"
    else
        warn "Metal MPS not detected — running on CPU"
    fi
}

# ---------------------------------------------------------------------------
# Convert a single file or target
# ---------------------------------------------------------------------------
convert_target() {
    local target="$1"
    local resolved="$target"

    # If it's a file path
    if [[ -f "$target" ]]; then
        local ext="${target##*.}"
        ext="$(echo "$ext" | tr '[:upper:]' '[:lower:]')"
        if [[ "$ext" != "pdf" && "$ext" != "epub" ]]; then
            warn "Skipping unsupported file type: $target"
            return
        fi
        local basename
        basename="$(basename "$target")"
        local dest="$BOOKS_DIR/$basename"
        if [[ "$(cd "$(dirname "$target")" && pwd)/$basename" != "$(cd "$BOOKS_DIR" && pwd)/$basename" ]]; then
            info "Copying → $dest"
            cp "$target" "$dest"
        fi
        resolved="$dest"
    fi

    header "Converting: $resolved"
    info "Voice: ${BOLD}${GREEN}$VOICE${RESET} | Speed: $SPEED | Format: $AUDIO_FORMAT | Workers: $CONCURRENCY | GPU: Apple Metal (MPS)"
    echo ""

    local cmd=(
        "$PYTHON" "$CONVERTER"
        "$resolved"
        --audio
        --epub
        --audio-format "$AUDIO_FORMAT"
        --voice "$VOICE"
        --speed "$SPEED"
        --concurrency "$CONCURRENCY"
        --endpoint "$KOKORO_ENDPOINT"
        --model kokoro
        --skip-front
        --strip-citations
        --drop-footnotes
        --audio-dir "$AUDIO_DIR"
        --books-dir "$BOOKS_DIR"
    )

    if "${cmd[@]}"; then
        success "Conversion finished for: $resolved"
    else
        error "Conversion failed for: $resolved"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
header "📚 Audiobook Factory — Kokoro Metal GPU"
info "Books dir:    $BOOKS_DIR"
info "Output dir:   $AUDIO_DIR"
info "TTS server:   $KOKORO_ENDPOINT"
info "Voice type:   ${BOLD}${GREEN}$VOICE${RESET}"
info "Speed:        ${SPEED}x"
info "Audio format: $AUDIO_FORMAT"
echo ""

start_kokoro_server

if [[ ${#FINAL_TARGETS[@]} -eq 0 ]]; then
    # No targets provided — batch mode: convert everything pending in Books dir
    info "Batch converting pending books in $BOOKS_DIR with voice: ${BOLD}${GREEN}$VOICE${RESET}"
    echo ""
    "$PYTHON" "$CONVERTER" \
        --all \
        --audio \
        --epub \
        --audio-format "$AUDIO_FORMAT" \
        --voice "$VOICE" \
        --speed "$SPEED" \
        --concurrency "$CONCURRENCY" \
        --endpoint "$KOKORO_ENDPOINT" \
        --model kokoro \
        --skip-front \
        --strip-citations \
        --drop-footnotes \
        --audio-dir "$AUDIO_DIR" \
        --books-dir "$BOOKS_DIR"
else
    # Process each provided file / index / name
    for arg in "${FINAL_TARGETS[@]}"; do
        convert_target "$arg"
    done
fi

echo ""
success "All done! Audiobooks are in: $AUDIO_DIR"
ls -lh "$AUDIO_DIR" 2>/dev/null || true
