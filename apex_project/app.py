from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from google import genai
from google.genai import types
import os
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ================= CONFIG =================
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fitness.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Shared flat-file used by both the web app and fitness_assistant.py CLI
FITNESS_DATA_FILE = Path("fitness_data.json")

db = SQLAlchemy(app)

# ================= MODELS =================
class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(100))
    email      = db.Column(db.String(100), unique=True)
    age        = db.Column(db.String(10))
    goal       = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    last_seen  = db.Column(db.DateTime, default=datetime.datetime.now)

class Workout(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'))
    username  = db.Column(db.String(100))
    type      = db.Column(db.String(100))
    lifts     = db.Column(db.Text)
    feel      = db.Column(db.String(50))
    duration  = db.Column(db.Integer)
    date      = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now)

with app.app_context():
    db.create_all()

# ================= HELPERS =================

def load_fitness_data() -> dict:
    """Load the flat-file JSON used by the CLI assistant."""
    if FITNESS_DATA_FILE.exists():
        try:
            return json.loads(FITNESS_DATA_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"profile": {}, "workouts": [], "nutrition": [], "history": []}

def save_fitness_data(data: dict):
    """Persist data back to JSON so CLI and web stay in sync."""
    FITNESS_DATA_FILE.write_text(json.dumps(data, indent=2))

def build_system_prompt(profile: dict) -> str:
    """Build the APEX coach system prompt from the saved profile."""
    return (
        "You are APEX, an elite AI fitness coach. Your client's profile:\n"
        f"Name: {profile.get('name', 'Athlete')}, "
        f"Age: {profile.get('age', '?')}, "
        f"Weight: {profile.get('weight_kg', profile.get('weight', '?'))}kg, "
        f"Height: {profile.get('height_cm', profile.get('height', '?'))}cm\n"
        f"Goal: {profile.get('goal', '?')}, "
        f"Experience: {profile.get('experience', '?')}, "
        f"Training days: {profile.get('days_per_week', profile.get('days', '?'))}/week\n"
        f"Equipment: {profile.get('equipment', '?')}, "
        f"Diet: {profile.get('dietary_pref', profile.get('diet', 'No restrictions'))}, "
        f"Injuries: {profile.get('injuries', 'None')}\n\n"
        "Be direct, specific, supportive, and science-backed. "
        "Personalize everything to this profile. "
        "For Indian users, Indian cuisine suggestions are welcome. "
        "Keep responses concise but helpful. "
        "Use formatting (bullet points, bold) when it helps clarity."
    )

# ================= ROUTES =================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/admin")
def admin_page():
    return render_template("admin.html")


# ─── PROFILE ─────────────────────────────────────────────────────────────────
@app.route("/profile", methods=["GET"])
def get_profile():
    data = load_fitness_data()
    return jsonify(data.get("profile", {}))

@app.route("/profile", methods=["POST"])
def update_profile():
    data    = load_fitness_data()
    payload = request.get_json()
    data["profile"].update(payload)
    save_fitness_data(data)
    return jsonify({"message": "Profile updated", "profile": data["profile"]})


# ─── CHAT ─────────────────────────────────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def chat():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not set on server"}), 500

    payload  = request.get_json()
    messages = payload.get("messages", [])
    system   = payload.get("system", "")

    # Fall back to building the system prompt from the saved profile
    if not system:
        fitness_data = load_fitness_data()
        system = build_system_prompt(fitness_data.get("profile", {}))

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Build conversation history for the new SDK
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system)
        )
        reply = response.text
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"response": reply})


# ─── WORKOUTS ─────────────────────────────────────────────────────────────────
@app.route("/workouts", methods=["GET"])
def get_workouts():
    data = load_fitness_data()
    return jsonify(data.get("workouts", []))

@app.route("/workouts", methods=["POST"])
def log_workout():
    payload = request.get_json()
    user_email = payload.get("email")
    user = User.query.filter_by(email=user_email).first()
    
    entry = {
        "date":     payload.get("date", datetime.date.today().isoformat()),
        "type":     payload.get("type", payload.get("name", "General Training")),
        "lifts":    payload.get("lifts", payload.get("notes", "")),
        "feel":     payload.get("feel", "Solid session"),
        "duration": payload.get("duration", 45),
    }
    
    # Save to DB if user exists
    if user:
        workout = Workout(
            user_id  = user.id,
            username = user.username,
            type     = entry["type"],
            lifts    = entry["lifts"],
            feel     = entry["feel"],
            duration = entry["duration"],
            date     = entry["date"]
        )
        db.session.add(workout)
        db.session.commit()
        
    # Also save to flat-file for CLI sync
    data = load_fitness_data()
    data["workouts"].append({
        "date":  entry["date"],
        "name":  entry["type"],
        "notes": entry["lifts"],
    })
    save_fitness_data(data)
    
    return jsonify({"message": "Workout logged", "entry": entry})

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    payload = request.get_json()
    email = payload.get("email")
    if not email:
        return jsonify({"error": "Email required"}), 400
    
    user = User.query.filter_by(email=email).first()
    if user:
        user.last_seen = datetime.datetime.now()
        db.session.commit()
        return jsonify({"status": "ok", "last_seen": user.last_seen.isoformat()})
    return jsonify({"error": "User not found"}), 404

@app.route("/generate_workout", methods=["POST"])
def generate_workout():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not set on server"}), 500
    
    payload = request.get_json()
    profile = payload.get("profile", {})
    
    prompt = f"Generate a {profile.get('days', 5)}-day workout plan. Profile: goal={profile.get('goal', 'fat loss')}, level={profile.get('experience', 'beginner')}, equipment={profile.get('equipment', 'full gym')}, weight={profile.get('weight', 50)}kg, height={profile.get('height', 157)}cm, injuries={profile.get('injuries', 'none')}. Return JSON array: [{{day,focus,color,exercises:[{{name,sets,reps,rest,type,note}}]}}]. Color is a hex color. Exercises should match equipment and level."
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction="Return ONLY a valid JSON array. No markdown fences, no explanation.")
        )
        raw = response.text.replace("```json", "").replace("```", "").strip()
        plan = json.loads(raw)
        return jsonify({"plan": plan})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate_nutrition", methods=["POST"])
def generate_nutrition():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not set on server"}), 500
    
    payload = request.get_json()
    profile = payload.get("profile", {})
    
    indian_pref = ", Indian cuisine preferred" if "indian" in profile.get('diet', '').lower() else " with Indian food options welcome"
    prompt = f"Create a practical daily meal plan. Profile: weight={profile.get('weight', 50)}kg, height={profile.get('height', 157)}cm, goal={profile.get('goal', 'fat loss')}, diet={profile.get('diet', 'no restrictions')}. Make it practical{indian_pref}. Return JSON array of 5 meals: [{{name,time,kcal,foods}}] where foods is a readable string."
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction="Return ONLY valid JSON array. No markdown, no explanation.")
        )
        raw = response.text.replace("```json", "").replace("```", "").strip()
        meals = json.loads(raw)
        return jsonify({"meals": meals})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── SAVE USER ────────────────────────────────────────────────────────────────
@app.route("/save_user", methods=["POST"])
def save_user():
    payload  = request.get_json()
    existing = User.query.filter_by(email=payload.get("email")).first()
    if existing:
        return jsonify({"message": "User already exists"}), 200

    user = User(
        username = payload.get("name"),
        email    = payload.get("email"),
        age      = payload.get("age", ""),
        goal     = payload.get("goal", ""),
    )
    db.session.add(user)
    db.session.commit()

    # Seed fitness_data.json profile on first signup if it's empty
    fitness_data = load_fitness_data()
    if not fitness_data.get("profile"):
        fitness_data["profile"] = {
            "name":         payload.get("name", ""),
            "age":          payload.get("age", ""),
            "goal":         payload.get("goal", ""),
            "weight_kg":    "",
            "height_cm":    "",
            "experience":   "beginner",
            "days_per_week": "3",
            "equipment":    "full gym",
            "dietary_pref": "no restrictions",
            "injuries":     "none",
        }
        save_fitness_data(fitness_data)

    return jsonify({"message": "User saved successfully"})


# ─── GET ALL USERS ────────────────────────────────────────────────────────────
@app.route("/users", methods=["GET"])
def get_users():
    users = User.query.all()
    now = datetime.datetime.now()
    results = []
    for u in users:
        # Consider online if seen in the last 2 minutes
        is_online = False
        if u.last_seen:
            diff = (now - u.last_seen).total_seconds()
            is_online = diff < 120 
        
        results.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "age": u.age,
            "goal": u.goal,
            "joined": u.created_at.strftime("%Y-%m-%d") if u.created_at else "—",
            "is_online": is_online
        })
    return jsonify(results)

@app.route("/admin/stats", methods=["GET"])
def get_admin_stats():
    total_users = User.query.count()
    
    # Joined today
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    joined_today = User.query.filter(User.created_at >= today_start).count()
    
    # Online now (last 2 mins)
    two_mins_ago = datetime.datetime.now() - datetime.timedelta(minutes=2)
    online_now = User.query.filter(User.last_seen >= two_mins_ago).count()
    
    # Recent workouts
    recent_workouts = Workout.query.order_by(Workout.timestamp.desc()).limit(10).all()
    workouts_list = [{
        "username": w.username,
        "type": w.type,
        "date": w.date,
        "duration": w.duration,
        "feel": w.feel
    } for w in recent_workouts]
    
    return jsonify({
        "total_users": total_users,
        "joined_today": joined_today,
        "online_now": online_now,
        "recent_workouts": workouts_list
    })

@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"}), 200
    return jsonify({"error": "User not found"}), 404


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
