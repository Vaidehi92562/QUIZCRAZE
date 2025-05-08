from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import random
from flask_socketio import SocketIO, emit, join_room
import eventlet  # ✅ Fix WebSocket Error

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ✅ MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Vaidehi@123'  # Change this
app.config['MYSQL_DB'] = 'quizcrazeretryagain'

mysql = MySQL(app)
socketio = SocketIO(app, async_mode="eventlet")  # ✅ Fix WebSocket Error

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

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
        mysql.connection.commit()
        cursor.close()

        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
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

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    data = request.json
    game_code = data.get("gameCode")

    if not game_code:
        return jsonify({"error": "Missing game code!"}), 400

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM multiplayersname WHERE game_code = %s AND is_host = 1", (game_code,))
    host = cursor.fetchone()

    if not host:
        return jsonify({"error": "Only the host can start the quiz!"}), 403

    cursor.execute("UPDATE multigames SET quiz_started = 1 WHERE game_code = %s", (game_code,))
    mysql.connection.commit()
    cursor.close()

    # ✅ Notify all players in the game that the quiz has started
    socketio.emit("quiz_started", {"gameCode": game_code}, room=game_code)

    return jsonify({"success": True})

@app.route('/multi_quiz_room')
def multi_quiz_room():
    game_code = request.args.get("gameCode")

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT category FROM multigames WHERE game_code = %s", (game_code,))
    game = cursor.fetchone()

    if not game:
        return "Invalid Game Code", 400

    category = game[0]

    cursor.execute("SELECT * FROM questions WHERE category = %s ORDER BY RAND() LIMIT 10", (category,))
    questions = cursor.fetchall()
    cursor.close()

    return render_template("multi_quiz_room.html", game_code=game_code, questions=questions)

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    data = request.json
    game_code = data.get("gameCode")
    username = session.get("username")  # ✅ Ensure user is logged in
    answers = data.get("answers")
    time_taken = data.get("timeTaken")

    if not username or not game_code:
        return jsonify({"success": False, "error": "Invalid session or game code."}), 400

    score = len(answers)  # ✅ Simple logic (Modify as needed)

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("UPDATE multiplayersname SET score = %s, time_taken = %s WHERE game_code = %s AND username = %s",
                   (score, time_taken, game_code, username))
    mysql.connection.commit()
    cursor.close()

    return jsonify({"success": True, "gameCode": game_code})

@app.route('/multi_result')
def multi_result():
    game_code = request.args.get("gameCode")
    username = session.get("username")

    if not username or not game_code:
        return "Invalid session or game code.", 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT score, time_taken FROM multiplayersname WHERE game_code = %s AND username = %s", 
                   (game_code, username))
    result = cursor.fetchone()
    cursor.close()

    if result:
        return render_template("multi_result.html", game_code=game_code, score=result['score'], time_taken=result['time_taken'])
    else:
        return "No result found for this game.", 404

@socketio.on("send_message")
def handle_message(data):
    game_code = data["gameCode"]
    username = data["username"]
    message = data["message"]

    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO chat_messages (game_code, username, message) VALUES (%s, %s, %s)",
                   (game_code, username, message))
    mysql.connection.commit()
    cursor.close()

    emit("receive_message", {"username": username, "message": message}, room=game_code)

@socketio.on("join_room")
def join_game(data):
    game_code = data["gameCode"]
    join_room(game_code)

@socketio.on("start_quiz")
def notify_players(data):
    game_code = data["gameCode"]
    emit("quiz_started", {"gameCode": game_code}, room=game_code)

if __name__ == '__main__':
    print("🚀 Running Flask with Eventlet...")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)  # ✅ FIX WebSocket Issue
