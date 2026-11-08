#!/usr/bin/env python3
"""
save_document_narrator_agent.py

Saves the "Document Narrator" custom agent persona prompt in Odysseus:
1. In SQLite database (crew_members table) for Odysseus Crew / Assistants.
2. In presets.json for Chat UI preset selector.
3. In prompts markdown file for reference.
"""

import os
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ODYSSEUS_DIR = Path("~/Documents/Docker/Odysseus")
DB_PATH = ODYSSEUS_DIR / "data" / "app.db"
PRESETS_PATH = ODYSSEUS_DIR / "data" / "presets.json"
PROMPTS_DIR = ODYSSEUS_DIR / "data" / "prompts"

AGENT_NAME = "Document Narrator"
AGENT_PROMPT = """You are an expert Document Narrator and Audio Research Companion inside Odysseus.
When I upload or share documents (PDFs, research articles, reports, or notes):
1. **Audio-First Formatting**: Rewrite the target content for spoken narration. Strip out table symbols, raw markdown syntax, unreadable URLs, and footnote numbers so the speech sounds completely natural.
2. **Pronunciation & Flow**: Write numbers, acronyms, and technical symbols in conversational format (e.g., "$5M" -> "five million dollars", "e.g." -> "for example").
3. **Structured Reading Modes**:
   - If I say "Read Chapter/Section X", provide the clean spoken script for that exact part.
   - If I say "Executive Briefing", summarize the key takeaways in a 2-to-3-minute spoken script.
4. **Trigger Voice Output**: Ensure your final response outputs clean text ready to be synthesized by the local Kokoro engine (`/v1/audio/speech`)."""

AGENT_GREETING = "Hello! I am your Document Narrator. Upload or share any PDF, markdown note, or research article, and I will prepare an audio-first spoken script ready for Kokoro synthesis."


def register_crew_member():
    print("[1/3] Registering in Odysseus SQLite crew_members table...")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # Check if Document Narrator already exists
    cursor.execute("SELECT id FROM crew_members WHERE name = ?", (AGENT_NAME,))
    row = cursor.fetchone()

    if row:
        agent_id = row[0]
        cursor.execute(
            """
            UPDATE crew_members
            SET personality = ?, greeting = ?, is_active = 1, updated_at = ?
            WHERE id = ?
            """,
            (AGENT_PROMPT, AGENT_GREETING, now, agent_id),
        )
        print(f"      ✓ Updated existing Crew Member '{AGENT_NAME}' (ID: {agent_id}).")
    else:
        agent_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO crew_members (
                id, owner, name, avatar, user_name, personality, model, endpoint_url,
                greeting, enabled_tools, session_id, is_active, sort_order,
                is_default_assistant, timezone, created_at, updated_at
            ) VALUES (
                ?, 'admin', ?, '🎙️', NULL, ?, NULL, NULL,
                ?, '["read_file","manage_documents","web_fetch"]', NULL, 1, 1,
                0, NULL, ?, ?
            )
            """,
            (agent_id, AGENT_NAME, AGENT_PROMPT, AGENT_GREETING, now, now),
        )
        print(f"      ✓ Created new Crew Member '{AGENT_NAME}' (ID: {agent_id}).")

    conn.commit()
    conn.close()


def register_preset():
    print("[2/3] Adding to Odysseus data/presets.json...")
    if PRESETS_PATH.exists():
        presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    else:
        presets = {}

    presets["document_narrator"] = {
        "name": AGENT_NAME,
        "temperature": 0.4,
        "max_tokens": 4096,
        "system_prompt": AGENT_PROMPT,
        "description": "Expert document reader & audio-first script generator."
    }

    PRESETS_PATH.write_text(json.dumps(presets, indent=2), encoding="utf-8")
    print("      ✓ Saved to presets.json under 'document_narrator'.")


def save_prompt_markdown():
    print("[3/3] Saving prompt documentation...")
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    prompt_file = PROMPTS_DIR / "document_narrator.md"
    prompt_file.write_text(f"# {AGENT_NAME} Persona\n\n{AGENT_PROMPT}\n", encoding="utf-8")
    
    # Also save in Speaches workspace
    speaches_prompt = Path("document_narrator_prompt.md")
    speaches_prompt.write_text(f"# {AGENT_NAME} Persona\n\n{AGENT_PROMPT}\n", encoding="utf-8")
    print(f"      ✓ Saved prompt to: {prompt_file} and {speaches_prompt.resolve()}")


def main():
    print("=== Saving Odysseus Document Narrator Agent Persona ===")
    register_crew_member()
    register_preset()
    save_prompt_markdown()
    print("=== Agent Persona Successfully Deployed! ===")


if __name__ == "__main__":
    main()
