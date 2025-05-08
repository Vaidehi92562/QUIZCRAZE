from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
import random
from flask_socketio import SocketIO, emit, join_room, leave_room

# ✅ Initialize Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ✅ Connect to MySQL database
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Vaidehi@123",     # ✨ Your MySQL password
    database="quizcrazeretryagain"   # ✨ Your database name
)

# ✅ Initialize SocketIO
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        return render_template('dashboard.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/multiplayer')
def multiplayer():
    return render_template("multi_choose.html")

@app.route('/multi_host')
def multi_host():
    return render_template("multi_host.html")

@app.route('/multi_join')
def multi_join():
    return render_template("multi_join.html")

@app.route('/multi_lobby')
def multi_lobby():
    game_code = request.args.get("gameCode")
    return render_template("multi_lobby.html", game_code=game_code)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        cursor = db.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
        db.commit()
        cursor.close()

        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            return render_template("login.html", error="Invalid email or password")
    return render_template("login.html")

@app.route('/create_game', methods=['POST'])
def create_game():
    data = request.json
    category = data.get("category")
    username = data.get("username")
    game_code = str(random.randint(100000, 999999))

    if not category or not username:
        return jsonify({"error": "Missing category or username"}), 400

    cursor = db.cursor()
    cursor.execute("INSERT INTO multigames (game_code, category) VALUES (%s, %s)", (game_code, category))
    cursor.execute("INSERT INTO multiplayersname (game_code, username, is_host) VALUES (%s, %s, 1)", (game_code, username))
    db.commit()
    cursor.close()

    return jsonify({"game_code": game_code, "message": "Game created successfully!", "host": username})

@app.route('/join_game', methods=['POST'])
def join_game():
    data = request.json
    game_code = data.get("gameCode")
    username = data.get("username")
    is_host = data.get("is_host", 0)

    if not (game_code and username):
        return jsonify({"error": "Missing game code or username!"}), 400

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM multigames WHERE game_code = %s", (game_code,))
    game = cursor.fetchone()

    if not game:
        return jsonify({"error": "Invalid game code!"}), 400

    cursor.execute("SELECT * FROM multiplayersname WHERE game_code = %s AND username = %s", (game_code, username))
    existing_player = cursor.fetchone()

    if existing_player:
        return jsonify({"error": "Player already joined!"}), 400

    cursor.execute("INSERT INTO multiplayersname (game_code, username, is_host) VALUES (%s, %s, %s)", (game_code, username, is_host))
    db.commit()
    cursor.close()

    return jsonify({"message": "Joined game successfully!", "is_host": is_host})

@app.route('/get_players', methods=['GET'])
def get_players():
    game_code = request.args.get("gameCode")

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT username, is_host FROM multiplayersname WHERE game_code = %s", (game_code,))
    players = cursor.fetchall()
    cursor.close()

    return jsonify({"players": players})

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    data = request.json
    game_code = data.get("gameCode")

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM multiplayersname WHERE game_code = %s AND is_host = 1", (game_code,))
    host = cursor.fetchone()

    if not host:
        return jsonify({"error": "Only the host can start the quiz!"}), 403

    cursor.execute("UPDATE multigames SET quiz_started = 1 WHERE game_code = %s", (game_code,))
    db.commit()
    cursor.close()

    socketio.emit("quiz_started", {"gameCode": game_code}, room=game_code)

    return jsonify({"success": True})

@app.route('/multi_quiz_room')
def multi_quiz_room():
    game_code = request.args.get('gameCode')
    username = session.get('username')

    if not game_code or not username:
        return "Invalid game session.", 400

    cursor = db.cursor()
    cursor.execute("SELECT category FROM multigames WHERE game_code = %s", (game_code,))
    game = cursor.fetchone()

    if not game:
        return "Game not found!", 400

    category = game[0]

    cursor.execute("SELECT id, question, option1, option2, option3, option4 FROM questions WHERE category = %s ORDER BY RAND() LIMIT 10", (category,))
    questions = cursor.fetchall()
    cursor.close()

    if not questions:
        return "No questions available for this category.", 400

    questions_list = []
    for q in questions:
        questions_list.append({
            "id": q[0],
            "question": q[1],
            "option1": q[2],
            "option2": q[3],
            "option3": q[4],
            "option4": q[5],
        })

    return render_template("multi_quiz_room.html", game_code=game_code, username=username, questions=questions_list)

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    data = request.json
    game_code = data.get('gameCode')
    username = data.get('username')
    user_answers = data.get('answers', {})
    time_taken = data.get('timeTaken', 0)

    if not user_answers:
        return jsonify({"error": "No answers provided!"}), 400

    cursor = db.cursor(dictionary=True)

    question_ids = tuple(user_answers.keys())
    format_strings = ','.join(['%s'] * len(question_ids))
    query = f"SELECT id, correct_option FROM questions WHERE id IN ({format_strings})"

    cursor.execute(query, question_ids)
    correct_answers = {str(row["id"]): str(row["correct_option"]) for row in cursor.fetchall()}

    answer_map = {"A": "1", "B": "2", "C": "3", "D": "4"}
    score = 0
    for qid, user_ans in user_answers.items():
        correct_ans = correct_answers.get(qid, None)
        user_ans_converted = answer_map.get(user_ans.strip().upper(), user_ans)
        if correct_ans and user_ans_converted == correct_ans:
            score += 1

    cursor.execute("""
        UPDATE multiplayersname 
        SET score = %s, time_taken = %s
        WHERE game_code = %s AND username = %s
    """, (score, time_taken, game_code, username))

    db.commit()
    cursor.close()

    return jsonify({
        "success": True,
        "redirect_url": f"/multi_result?gameCode={game_code}&username={username}"
    })

@app.route('/multi_result')
def multi_result():
    game_code = request.args.get('gameCode')
    username = request.args.get('username')

    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT score, time_taken FROM multiplayersname 
        WHERE game_code = %s AND username = %s
    """, (game_code, username))

    result = cursor.fetchone()
    cursor.close()

    if result:
        return render_template(
            "multi_result.html",
            game_code=game_code,
            username=username,
            score=result['score'],
            time_taken=result['time_taken']
        )
    else:
        return "❌ No result found!", 404

@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    game_code = request.args.get('gameCode')

    if not game_code:
        return render_template("leaderboard.html", error="Game code is required!")

    cursor = db.cursor()
    cursor.execute("""
        SELECT username, score, time_taken
        FROM multiplayersname
        WHERE game_code = %s
        ORDER BY score DESC, time_taken ASC
    """, (game_code,))

    players = cursor.fetchall()
    cursor.close()

    if not players:
        return render_template("leaderboard.html", error="No players found for this game code!")

    players_list = [{"username": p[0], "score": p[1], "time_taken": p[2]} for p in players]

    return render_template("leaderboard.html", players=players_list, game_code=game_code)

# ✅ SOCKET.IO SECTION

@socketio.on("send_message")
def handle_message(data):
    game_code = data["gameCode"]
    username = data["username"]
    message = data["message"]

    cursor = db.cursor()
    cursor.execute("INSERT INTO chat_messages (game_code, username, message) VALUES (%s, %s, %s)", (game_code, username, message))
    db.commit()
    cursor.close()

    emit("receive_message", {"username": username, "message": message}, room=game_code)

@socketio.on("join_room")
def handle_join_room(data):
    game_code = data["gameCode"]
    join_room(game_code)
    print(f"Player joined room: {game_code}")

# ✅ Run the server
if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host="0.0.0.0")
