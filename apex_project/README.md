# APEX — AI Fitness Coach

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set your Gemini API key:
   ```
   # Windows
   set GEMINI_API_KEY=AIzaSy...

   # Mac / Linux
   export GEMINI_API_KEY=AIzaSy...
   ```

3. Run the web app:
   ```
   python app.py
   ```
   Then open http://localhost:5000

4. (Optional) Run the CLI assistant:
   ```
   python fitness_assistant.py
   ```

## Project Structure
```
apex_project/
├── app.py                  # Flask web server
├── fitness_assistant.py    # Terminal CLI coach
├── fitness_data.json       # Shared profile + workout history
├── fitness.db              # SQLite user database
├── requirements.txt
└── templates/
    └── index.html          # Frontend UI
```
