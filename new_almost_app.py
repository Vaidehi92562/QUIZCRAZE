from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import random
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
 
from flask_socketio import SocketIO, emit, join_room

# ✅ Initialize Flask-SocketIO


 
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ✅ MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Vaidehi@123'  # Change this
app.config['MYSQL_DB'] = 'quizcrazeretryagain'

mysql = MySQL(app)


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


@app.route('/create_game', methods=['POST'])
def create_game():
    data = request.json
    category = data.get("category")
    username = data.get("username")  # Get the host's username
    game_code = str(random.randint(100000, 999999))  # Generate 6-digit game code

    if not category or not username:
        return jsonify({"error": "Missing category or username"}), 400

    cursor = mysql.connection.cursor()

    # ✅ Insert game into `multigames`
    cursor.execute("INSERT INTO multigames (game_code, category) VALUES (%s, %s)", (game_code, category))

    # ✅ Insert the host into `multiplayersname`
    cursor.execute("INSERT INTO multiplayersname (game_code, username, is_host) VALUES (%s, %s, 1)", 
                   (game_code, username))
    
    mysql.connection.commit()
    cursor.close()

    return jsonify({"game_code": game_code, "message": "Game created successfully!", "host": username})




@app.route('/join_game', methods=['POST'])
def join_game():
    data = request.json
    game_code = data.get("gameCode")
    username = data.get("username")
    is_host = data.get("is_host", 0)  # Default to 0 for regular players

    if not (game_code and username):
        return jsonify({"error": "Missing game code or username!"}), 400

    cursor = mysql.connection.cursor()

    # ✅ Check if the game exists
    cursor.execute("SELECT * FROM multigames WHERE game_code = %s", (game_code,))
    game = cursor.fetchone()
    
    if not game:
        return jsonify({"error": "Invalid game code!"}), 400

    # ✅ Check if player already exists
    cursor.execute("SELECT * FROM multiplayersname WHERE game_code = %s AND username = %s", (game_code, username))
    existing_player = cursor.fetchone()

    if existing_player:
        return jsonify({"error": "Player already joined!"}), 400

    # ✅ Insert player into `multiplayersname`
    cursor.execute("INSERT INTO multiplayersname (game_code, username, is_host) VALUES (%s, %s, %s)", 
                   (game_code, username, is_host))

    mysql.connection.commit()
    cursor.close()

    return jsonify({"message": "Joined game successfully!", "is_host": is_host})



@app.route('/get_players', methods=['GET'])
def get_players():
    game_code = request.args.get("gameCode")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT username, is_host FROM multiplayersname WHERE game_code = %s", (game_code,))
    players = cursor.fetchall()
    cursor.close()

    return jsonify({"players": players})  # Host will now be included

from flask_socketio import SocketIO, emit

# Ensure SocketIO is initialized correctly
socketio = SocketIO(app)

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    data = request.json
    game_code = data.get("gameCode")

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM multiplayersname WHERE game_code = %s AND is_host = 1", (game_code,))
    host = cursor.fetchone()

    if not host:
        return jsonify({"error": "Only the host can start the quiz!"}), 403

    # ✅ Mark the quiz as started
    cursor.execute("UPDATE multigames SET quiz_started = 1 WHERE game_code = %s", (game_code,))
    mysql.connection.commit()
    cursor.close()

    # ✅ Broadcast event to all players
    socketio.emit("quiz_started", {"gameCode": game_code}, room=game_code)

    return jsonify({"success": True})




socketio = SocketIO(app)  # Initialize SocketIO

@app.route('/multi_quiz_room')
def multi_quiz_room():
    game_code = request.args.get("gameCode")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT category FROM multigames WHERE game_code = %s", (game_code,))
    game = cursor.fetchone()

    if not game:
        return "Invalid Game Code", 400

    category = game["category"]

    # ✅ Fetch 10 Random Questions from the Database
    cursor.execute("""
        SELECT id, question, option1, option2, option3, option4, correct_option 
        FROM questions 
        WHERE category = %s 
        ORDER BY RAND() 
        LIMIT 10
    """, (category,))
    questions = cursor.fetchall()
    cursor.close()

    if not questions:
        return render_template("multi_quiz_room.html", game_code=game_code, questions=None)

    return render_template("multi_quiz_room.html", game_code=game_code, questions=questions)


@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    data = request.json
    game_code = data.get('gameCode')
    username = data.get('username')
    user_answers = data.get('answers', {})
    time_taken = data.get('timeTaken', 0)

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ✅ Fetch correct answers from the database
    cursor.execute("SELECT id, correct_option FROM questions WHERE id IN %s", 
                   (tuple(user_answers.keys()),))
    correct_answers = {str(row["id"]): str(row["correct_option"]) for row in cursor.fetchall()}

    print(f"🔵 Received Answers from {username}: {user_answers}")
    print(f"🟢 Correct Answers from DB: {correct_answers}")

    # ✅ Mapping of A, B, C, D → 1, 2, 3, 4
    answer_map = {"A": "1", "B": "2", "C": "3", "D": "4"}

    # ✅ Calculate the score correctly
    score = 0
    for question_id, user_answer in user_answers.items():
        correct_answer = correct_answers.get(question_id, None)

        # Convert user answer from letter (A, B, C, D) → number (1, 2, 3, 4)
        user_answer_converted = answer_map.get(user_answer.strip().upper(), None)

        # Debugging: Print values and their types
        print(f"🔍 Checking QID {question_id}:")
        print(f"   → User Answer (Converted): {user_answer_converted} | Type: {type(user_answer_converted)}")
        print(f"   → Correct Answer (DB): {correct_answer} | Type: {type(correct_answer)}")

        # Ensure both are converted to **strings** before comparison
        if correct_answer is not None and user_answer_converted == correct_answer:
            print(f"✅ Match Found for QID {question_id} → +1 Point")
            score += 1
        else:
            print(f"❌ No Match for QID {question_id} → +0 Points")

    print(f"✅ Final Calculated Score for {username} = {score}")

    # ✅ Store the result in MySQL
    cursor.execute(
        """UPDATE multiplayersname 
           SET score = %s, time_taken = %s
           WHERE game_code = %s AND username = %s""",
        (score, time_taken, game_code, username)
    )

    mysql.connection.commit()
    cursor.close()

    return jsonify({"success": True, "score": score, "time_taken": time_taken})





@app.route('/multi_result')
def multi_result():
    game_code = request.args.get("gameCode")
    username = session.get("username")

    print("Fetching result for Game Code:", game_code)
    print("Username in session:", username)

    if not username or not game_code:
        return "Invalid session or game code.", 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT score, time_taken FROM results WHERE game_code = %s AND username = %s",
                   (game_code, username))
    result = cursor.fetchone()
    cursor.close()

    print("Result fetched from MySQL:", result)

    if result:
        return render_template("multi_result.html", 
                               game_code=game_code, 
                               score=result['score'], 
                               time_taken=result['time_taken'])
    else:
        return "No result found for this game.", 404


@app.route('/leaderboard')
def leaderboard():
    game_code = request.args.get("gameCode")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT username, score, time_taken
        FROM results
        WHERE game_code = %s
        ORDER BY score DESC, time_taken ASC
    """, (game_code,))
    
    players = cursor.fetchall()
    cursor.close()

    return jsonify({"players": players})



@socketio.on("send_message")
def handle_message(data):
    game_code = data["gameCode"]
    message = data["message"]

    # ✅ Broadcast message to all players in the room
    emit("receive_message", {"message": message}, room=game_code)



@socketio.on("join_room")
def handle_join_room(data):
    game_code = data["gameCode"]
    join_room(game_code)  # ✅ Add the player to the room
    print(f"Player joined room: {game_code}")  # Debugging purpose




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

    # ✅ Emit Message to All Clients in the Room
    emit("receive_message", {"username": username, "message": message}, room=game_code)





if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host="0.0.0.0")
