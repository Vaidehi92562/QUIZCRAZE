from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import random
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
 
 
 
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



@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    game_code = request.args.get("gameCode")

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM multiplayersname WHERE game_code = %s AND is_host = 1", (game_code,))
    host = cursor.fetchone()

    if not host:
        return jsonify({"error": "Only the host can start the quiz!"}), 403

    cursor.execute("UPDATE multigames SET quiz_started = 1 WHERE game_code = %s", (game_code,))
    mysql.connection.commit()
    cursor.close()

    return jsonify({"success": True})





socketio = SocketIO(app)  # Initialize SocketIO

@app.route('/multi_quiz_room')
def multi_quiz_room():
    game_code = request.args.get("gameCode")

    # ✅ Fetch category for this game
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT category FROM multigames WHERE game_code = %s", (game_code,))
    game = cursor.fetchone()

    if not game:
        return "Invalid Game Code", 400

    category = game[0]  # Extract category

    # ✅ Fetch 10 random questions from MySQL
    cursor.execute("SELECT * FROM questions WHERE category = %s ORDER BY RAND() LIMIT 10", (category,))
    questions = cursor.fetchall()
    cursor.close()

    return render_template("multi_quiz_room.html", game_code=game_code, questions=questions)



@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    data = request.json
    game_code = data.get("gameCode")
    answers = data.get("answers")

    cursor = mysql.connection.cursor()

    # ✅ Fetch correct answers from DB
    cursor.execute("SELECT id, correct_option FROM questions WHERE category = (SELECT category FROM multigames WHERE game_code = %s)", (game_code,))
    correct_answers = dict(cursor.fetchall())

    score = 0
    for q_id, answer in answers.items():
        if correct_answers.get(int(q_id)) == answer:
            score += 10  # ✅ Assign 10 points per correct answer

    # ✅ Store player score
    cursor.execute("UPDATE multiplayersname SET score = %s WHERE game_code = %s AND username = %s", 
                   (score, game_code, session.get("username")))
    
    mysql.connection.commit()
    cursor.close()

    # ✅ Notify all players to update leaderboard
    socketio.emit("update_leaderboard", room=game_code)

    return jsonify({"message": "Quiz submitted! Your score: " + str(score)})


@app.route('/leaderboard')
def leaderboard():
    game_code = request.args.get("gameCode")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT username, score FROM multiplayersname WHERE game_code = %s ORDER BY score DESC", (game_code,))
    players = cursor.fetchall()
    cursor.close()

    return jsonify({"players": players})


@socketio.on("send_message")
def handle_message(data):
    game_code = data["gameCode"]
    message = data["message"]

    # ✅ Broadcast message to all players in the room
    emit("receive_message", {"message": message}, room=game_code)

@socketio.on("start_quiz")
def handle_start_quiz(data):
    game_code = data["gameCode"]
    print(f"🔥 Quiz Started for Game Code: {game_code}")

    # ✅ Broadcast to all players in the game room
    emit("redirect_to_quiz", {"gameCode": game_code}, room=game_code)


@socketio.on("join_room")
def handle_join_room(data):
    game_code = data["gameCode"]
    join_room(game_code)  # ✅ Add player to the game room



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




@socketio.on("join_room")
def join_game(data):
    game_code = data["gameCode"]
    join_room(game_code)



if __name__ == '__main__':
    app.run(debug=True)
