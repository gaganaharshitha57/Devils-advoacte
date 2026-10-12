from flask import Flask, render_template, request, session, redirect, url_for
from groq import Groq
import sqlite3
import json
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-this")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def create_database():
    connection = sqlite3.connect("database.db")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            customers TEXT,
            budget TEXT,
            result_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            customers TEXT,
            budget TEXT,
            result_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


@app.route("/")
def home():
    return render_template("index.html")
    
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")
@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row

    records = connection.execute("""
        SELECT id, title, budget, created_at
        FROM evaluation_history
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()

    connection.close()

    ist_records = []

    for record in records:
        item = dict(record)

        utc_time = datetime.strptime(
            item["created_at"], "%Y-%m-%d %H:%M:%S"
        )

        ist_time = utc_time + timedelta(hours=5, minutes=30)

        item["created_at"] = ist_time.strftime(
            "%Y-%m-%d %I:%M:%S %p"
        )

        ist_records.append(item)

    return render_template(
        "history.html",
        records=ist_records
    )

@app.route("/evaluate", methods=["GET", "POST"])
def evaluate():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        customers = request.form["customers"]
        budget = request.form["budget"]

        prompt = f"""
You are Devil's Advocate, an AI business idea evaluator.

Analyze this business idea critically.

Business Idea: {title}
Description: {description}
Target Customers: {customers}
Estimated Investment: {budget}

Give a simple evaluation covering:
1. Strengths
2. Weaknesses
3. Risks
4. Market concerns
5. Final verdict

Be realistic and concise.
"""

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": "You are Devil's Advocate, a smart and honest friend reviewing a business idea. Use simple everyday English that anyone can understand. Keep every point short, clear and meaningful. Avoid complicated business words and unnecessary details. Explain the good and bad sides honestly and give practical advice. Make the answer sound natural, friendly and human, not robotic or like a business textbook."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "business_evaluation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "readiness_score": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100
                            },
                            "strengths": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "weaknesses": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "opportunities": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "threats": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "risks": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "suggestions": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "verdict": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "readiness_score",
                            "strengths",
                            "weaknesses",
                            "opportunities",
                            "threats",
                            "risks",
                            "suggestions",
                            "verdict"
                        ],
                        "additionalProperties": False
                    }
                }
            }
        )

        evaluation = json.loads(
            response.choices[0].message.content
        )
        if "user_id" not in session:
            return redirect(url_for("login"))

        connection = sqlite3.connect("database.db")

        connection.execute("""
            INSERT INTO evaluation_history
            (user_id, title, description, customers, budget, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            title,
            description,
            customers,
            budget,
            json.dumps(evaluation)
        ))

        connection.commit()
        connection.close()

        return render_template(
            "result.html",
            title=title,
            description=description,
            customers=customers,
            budget=budget,
            readiness_score=evaluation["readiness_score"],
            strengths=evaluation["strengths"],
            weaknesses=evaluation["weaknesses"],
            opportunities=evaluation["opportunities"],
            threats=evaluation["threats"],
            risks=evaluation["risks"],
            suggestions=evaluation["suggestions"],
            verdict=evaluation["verdict"]
        )

    return render_template("evaluate.html")
@app.route("/result")
def result():
    return render_template("result.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = sqlite3.connect("database.db")

        user = connection.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()

        connection.close()

        if user:
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            return redirect(url_for("dashboard"))

        return "Invalid email or password!"
    return render_template("login.html")
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"]
        new_password = request.form["password"]

        connection = sqlite3.connect("database.db")

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if user:
            connection.execute(
                "UPDATE users SET password = ? WHERE email = ?",
                (new_password, email)
            )

            connection.commit()
            connection.close()

            return "Password changed successfully!"

        connection.close()
        return "Email not found!"

    return render_template("forgot_password.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        if len(password) < 8:
            return render_template(
                "register.html",
                message="Password must be at least 8 characters long."
            )

        if not any(char.isupper() for char in password):
            return render_template(
                "register.html",
                message="Password must contain at least one uppercase letter."
            )

        if not any(char.islower() for char in password):
            return render_template(
                "register.html",
                message="Password must contain at least one lowercase letter."
            )

        if not any(char.isdigit() for char in password):
            return render_template(
                "register.html",
                message="Password must contain at least one number."
            )

        if not any(not char.isalnum() for char in password):
            return render_template(
                "register.html",
                message="Password must contain at least one special character."
            )

        connection = sqlite3.connect("database.db")

        existing_user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            connection.close()
            return render_template(
                "register.html",
                message="Email already registered. Please login instead."
            )

        connection.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, password)
        )

        connection.commit()
        connection.close()

        return render_template("success.html")

    return render_template("register.html")

@app.route("/history/<int:record_id>")
def history_detail(record_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row

    record = connection.execute("""
        SELECT * FROM evaluation_history
        WHERE id = ? AND user_id = ?
    """, (record_id, session["user_id"])).fetchone()

    connection.close()

    if record is None:
        return "Evaluation not found.", 404

    evaluation = json.loads(record["result_json"])

    return render_template(
        "result.html",
        title=record["title"],
        description=record["description"],
        customers=record["customers"],
        budget=record["budget"],
        readiness_score=evaluation["readiness_score"],
        strengths=evaluation["strengths"],
        weaknesses=evaluation["weaknesses"],
        opportunities=evaluation["opportunities"],
        threats=evaluation["threats"],
        risks=evaluation["risks"],
        suggestions=evaluation["suggestions"],
        verdict=evaluation["verdict"]
    )
@app.route("/history/delete/<int:record_id>", methods=["POST"])
def delete_history(record_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = sqlite3.connect("database.db")

    connection.execute(
        """
        DELETE FROM evaluation_history
        WHERE id = ? AND user_id = ?
        """,
        (record_id, session["user_id"])
    )

    connection.commit()
    connection.close()

    return redirect(url_for("history"))
@app.route("/idea-gallery")
def idea_gallery():
    print("Unsplash key loaded:",bool(UNSPLASH_ACCESS_KEY))
    idea = request.args.get("idea", "").strip()
    images = []
    print("KEY LOADED:", bool(UNSPLASH_ACCESS_KEY))
    print("IDEA RECEIVED:", idea)
    if idea and UNSPLASH_ACCESS_KEY:
        try:
            response = requests.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": idea,
                    "per_page": 5,
                    "orientation": "landscape"
                },
                headers={
                    "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"
                },
                timeout=10
            )

            response.raise_for_status()
            results = response.json().get("results", [])

            for photo in results:
                photographer_url = (
                    photo["user"]["links"]["html"]
                    + "?utm_source=devils_advocate"
                    + "&utm_medium=referral"
                )

                unsplash_url = (
                    photo["links"]["html"]
                    + "?utm_source=devils_advocate"
                    + "&utm_medium=referral"
                )

                images.append({
                    "url": photo["urls"]["regular"],
                    "alt": photo.get("alt_description") or idea,
                    "photographer": photo["user"]["name"],
                    "photographer_url": photographer_url,
                    "unsplash_url": unsplash_url
                })

        except requests.RequestException as error:
            print("Unsplash image search failed:", error)

    return render_template(
        "idea_gallery.html",
        idea=idea,
        images=images
    )

if __name__ == "__main__":
    create_database()
    app.run(host="0.0.0.0", port=5000, debug=True)