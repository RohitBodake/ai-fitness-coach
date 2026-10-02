"""
AI-Powered Fitness Assistant
============================
A comprehensive fitness assistant using the Anthropic Claude API.
Covers: workout planning, exercise tracking, nutrition advice, and conversational AI.

Requirements:
    pip install anthropic rich typer

Usage:
    python fitness_assistant.py
"""

import json
import os
import datetime
from pathlib import Path
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ─── Optional pretty-printing (graceful fallback) ────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich import print as rprint
    console = Console()
    RICH = True
except ImportError:
    RICH = False
    console = None

# ─── Gemini Client ─────────────────────────────────────────────────────────
API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
MODEL  = "gemini-2.5-flash"

# ─── Persistent storage (JSON flat-file) ─────────────────────────────────────
DATA_FILE = Path("fitness_data.json")

def load_data() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {"profile": {}, "workouts": [], "nutrition": [], "history": []}

def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2))

# ─── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are an elite AI fitness coach with expertise in:
- Personalized workout programming (strength, hypertrophy, cardio, flexibility)
- Exercise science and biomechanics
- Sports nutrition and meal planning
- Recovery, sleep, and performance optimization
- Tracking progress and adjusting plans over time

You have access to the user's profile and history. Be specific, science-backed,
and encouraging. When generating workout plans or meal plans, always output valid
JSON wrapped in ```json ... ``` fences so the app can parse and store them.

Workout JSON schema:
{
  "type": "workout_plan",
  "name": "...",
  "goal": "...",
  "days_per_week": 3,
  "sessions": [
    {
      "day": "Monday",
      "focus": "Push",
      "exercises": [
        {"name": "...", "sets": 3, "reps": "8-12", "rest_seconds": 90, "notes": "..."}
      ]
    }
  ]
}

Nutrition JSON schema:
{
  "type": "nutrition_plan",
  "daily_calories": 2400,
  "macros": {"protein_g": 180, "carbs_g": 240, "fat_g": 80},
  "meals": [
    {"name": "Breakfast", "foods": [...], "calories": 600}
  ]
}
""".strip()

# ─── Core AI call ─────────────────────────────────────────────────────────────
def ask_gemini(user_message: str, history: list, profile: dict) -> str:
    profile_str = json.dumps(profile, indent=2) if profile else "No profile set yet."
    system = SYSTEM_PROMPT + f"\n\nUser Profile:\n{profile_str}"

    messages = history[-20:] + [{"role": "user", "content": user_message}]
    
    model = genai.GenerativeModel(MODEL, system_instruction=system)
    
    gemini_messages = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        gemini_messages.append({"role": role, "parts": [msg["content"]]})

    response = model.generate_content(gemini_messages)
    return response.text

# ─── Parse structured plans from Claude's response ────────────────────────────
def extract_json_blocks(text: str) -> list[dict]:
    import re
    blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    results = []
    for block in blocks:
        try:
            results.append(json.loads(block))
        except json.JSONDecodeError:
            pass
    return results

# ─── Display helpers ──────────────────────────────────────────────────────────
def print_header():
    if RICH:
        console.print(Panel.fit(
            "[bold cyan]⚡ AI FITNESS ASSISTANT[/bold cyan]\n"
            "[dim]Powered by Gemini · Your personal coach[/dim]",
            border_style="cyan"
        ))
    else:
        print("\n" + "="*50)
        print("  AI FITNESS ASSISTANT  — Powered by Gemini")
        print("="*50 + "\n")

def print_workout_plan(plan: dict):
    if RICH:
        console.print(f"\n[bold green]📋 {plan['name']}[/bold green] — Goal: {plan['goal']}")
        for session in plan.get("sessions", []):
            t = Table(title=f"[cyan]{session['day']} — {session['focus']}[/cyan]", show_lines=True)
            t.add_column("Exercise", style="bold")
            t.add_column("Sets")
            t.add_column("Reps")
            t.add_column("Rest (s)")
            t.add_column("Notes", style="dim")
            for ex in session.get("exercises", []):
                t.add_row(
                    ex["name"],
                    str(ex.get("sets", "")),
                    str(ex.get("reps", "")),
                    str(ex.get("rest_seconds", "")),
                    ex.get("notes", ""),
                )
            console.print(t)
    else:
        print(f"\n[WORKOUT] {plan['name']} | Goal: {plan['goal']}")
        for session in plan.get("sessions", []):
            print(f"\n  {session['day']} — {session['focus']}")
            for ex in session.get("exercises", []):
                print(f"    • {ex['name']}: {ex.get('sets')}x{ex.get('reps')} | rest {ex.get('rest_seconds')}s")

def print_nutrition_plan(plan: dict):
    macros = plan.get("macros", {})
    if RICH:
        console.print(
            f"\n[bold yellow]🥗 Nutrition Plan[/bold yellow] — "
            f"{plan.get('daily_calories')} kcal/day | "
            f"P: {macros.get('protein_g')}g · C: {macros.get('carbs_g')}g · F: {macros.get('fat_g')}g"
        )
        for meal in plan.get("meals", []):
            console.print(f"  [green]{meal['name']}[/green] ({meal.get('calories', '?')} kcal): "
                          + ", ".join(meal.get("foods", [])))
    else:
        print(f"\n[NUTRITION] {plan.get('daily_calories')} kcal/day | "
              f"P:{macros.get('protein_g')}g C:{macros.get('carbs_g')}g F:{macros.get('fat_g')}g")
        for meal in plan.get("meals", []):
            print(f"  {meal['name']} ({meal.get('calories')} kcal): {', '.join(meal.get('foods', []))}")

def show_history(data: dict):
    workouts = data.get("workouts", [])
    if RICH:
        t = Table(title="📊 Logged Workouts", show_lines=True)
        t.add_column("Date")
        t.add_column("Plan Name")
        t.add_column("Notes")
        for w in workouts[-10:]:
            t.add_row(w.get("date", ""), w.get("name", ""), w.get("notes", ""))
        console.print(t)
    else:
        print("\n[HISTORY] Last workouts:")
        for w in workouts[-10:]:
            print(f"  {w.get('date')} | {w.get('name')} | {w.get('notes')}")

# ─── Profile setup ────────────────────────────────────────────────────────────
def setup_profile(data: dict) -> dict:
    print("\n[Setup] Let's build your fitness profile.\n")
    fields = [
        ("name",            "Your name"),
        ("age",             "Age"),
        ("weight_kg",       "Weight (kg)"),
        ("height_cm",       "Height (cm)"),
        ("goal",            "Primary goal (e.g. fat loss, muscle gain, endurance)"),
        ("experience",      "Training experience (beginner/intermediate/advanced)"),
        ("days_per_week",   "Days per week available to train"),
        ("equipment",       "Equipment available (e.g. full gym, dumbbells, bodyweight)"),
        ("dietary_pref",    "Dietary preferences / restrictions"),
        ("injuries",        "Any injuries or limitations (or 'none')"),
    ]
    profile = {}
    for key, label in fields:
        if RICH:
            profile[key] = Prompt.ask(f"  [cyan]{label}[/cyan]")
        else:
            profile[key] = input(f"  {label}: ").strip()
    data["profile"] = profile
    save_data(data)
    print("\n✅ Profile saved!\n")
    return data

# ─── Log a workout session ────────────────────────────────────────────────────
def log_workout(data: dict):
    if RICH:
        notes = Prompt.ask("[cyan]Log today's workout — brief notes[/cyan]")
        name  = Prompt.ask("[cyan]Workout name or type[/cyan]", default="General Training")
    else:
        name  = input("Workout name/type: ").strip() or "General Training"
        notes = input("Brief notes (exercises, feel, PRs): ").strip()

    entry = {
        "date":  datetime.date.today().isoformat(),
        "name":  name,
        "notes": notes,
    }
    data["workouts"].append(entry)
    save_data(data)
    print("✅ Workout logged.\n")

# ─── Main chat loop ───────────────────────────────────────────────────────────
def chat_loop(data: dict):
    history: list = data.get("history", [])

    if RICH:
        console.print("\n[dim]Type your message, or use shortcuts:[/dim]")
        console.print("[dim]  /plan    → generate a workout plan[/dim]")
        console.print("[dim]  /meal    → generate a nutrition plan[/dim]")
        console.print("[dim]  /log     → log today's workout[/dim]")
        console.print("[dim]  /history → view past workouts[/dim]")
        console.print("[dim]  /profile → update your profile[/dim]")
        console.print("[dim]  /quit    → exit[/dim]\n")
    else:
        print("\nCommands: /plan /meal /log /history /profile /quit\n")

    while True:
        try:
            if RICH:
                user_input = Prompt.ask("[bold cyan]You[/bold cyan]").strip()
            else:
                user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue

        # ── Shortcuts ──
        if user_input == "/quit":
            print("👋 Stay consistent. See you next time!")
            break
        elif user_input == "/log":
            log_workout(data)
            continue
        elif user_input == "/history":
            show_history(data)
            continue
        elif user_input == "/profile":
            data = setup_profile(data)
            continue
        elif user_input == "/plan":
            user_input = (
                "Generate a detailed, personalised weekly workout plan for me "
                "based on my profile. Output it as JSON."
            )
        elif user_input == "/meal":
            user_input = (
                "Generate a detailed daily nutrition plan and sample meal plan for me "
                "based on my profile and goals. Output it as JSON."
            )

        # ── Call Gemini ──
        if RICH:
            with console.status("[dim]Thinking...[/dim]", spinner="dots"):
                reply = ask_gemini(user_input, history, data["profile"])
        else:
            print("...")
            reply = ask_gemini(user_input, history, data["profile"])

        # ── Parse & persist structured plans ──
        for block in extract_json_blocks(reply):
            btype = block.get("type")
            if btype == "workout_plan":
                data["workouts"].append({
                    "date": datetime.date.today().isoformat(),
                    "plan": block,
                    "name": block.get("name", "Plan"),
                    "notes": "AI-generated plan",
                })
                print_workout_plan(block)
            elif btype == "nutrition_plan":
                data["nutrition"].append({
                    "date": datetime.date.today().isoformat(),
                    "plan": block,
                })
                print_nutrition_plan(block)

        # ── Display reply ──
        clean_reply = reply  # show full reply including JSON for transparency
        if RICH:
            console.print(f"\n[bold green]Coach[/bold green]: {clean_reply}\n")
        else:
            print(f"\nCoach: {clean_reply}\n")

        # ── Update history ──
        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": reply})
        data["history"] = history[-40:]  # keep last 40 turns
        save_data(data)

# ─── Entry point ──────────────────────────────────────────────────────────────
def main():
    print_header()
    data = load_data()

    if not data.get("profile"):
        print("👋 Welcome! Let's start by setting up your profile.\n")
        data = setup_profile(data)
    else:
        name = data["profile"].get("name", "Athlete")
        print(f"\nWelcome back, {name}! 💪\n")

    chat_loop(data)

if __name__ == "__main__":
    main()
