from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import datetime
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ✅ MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Vaidehi@123'  # Change this
app.config['MYSQL_DB'] = 'quizcrazeretryagain'

mysql = MySQL(app)

# ✅ Home Page
@app.route('/')
def index():
    return render_template('index.html')

# ✅ Register Page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            return jsonify({"error": "All fields are required"}), 400

        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s)', (username, email, password))
        mysql.connection.commit()
        cursor.close()

        return redirect(url_for('login'))
    return render_template('register.html')

# ✅ Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            return render_template("login.html", error="Missing email or password")

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

# ✅ Dashboard Page
@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        return render_template('dashboard.html', username=session['username'])
    return redirect(url_for('login'))

# ✅ Get Questions for Selected Category
@app.route('/get_questions')
def get_questions():
    category = request.args.get('category')
    if not category:
        return jsonify({"error": "Category is required"}), 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    query = "SELECT question, option1, option2, option3, option4, correct_option FROM questions WHERE category = %s ORDER BY RAND() LIMIT 10"
    cursor.execute(query, (category,))
    questions = cursor.fetchall()
    cursor.close()

    return jsonify(questions)

# ✅ Singleplayer Mode
@app.route('/singleplayer')
def singleplayer():
    if 'user_id' in session:
        return render_template('singleplayer.html')
    return redirect(url_for('login'))

@app.route('/singleplayer_quiz')
def singleplayer_quiz():
    category = request.args.get('category', 'C')
    return render_template('singleplayer_quiz.html', category=category)

# ✅ Submit Singleplayer Score
@app.route('/submit_singleplayer_score', methods=['POST'])
def submit_singleplayer_score():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized access"}), 403

    data = request.json
    user_id = session['user_id']
    category = data.get('category')
    score = data.get('score')
    time_taken = data.get('time_taken')

    if not (category and score is not None and time_taken is not None):
        return jsonify({"error": "Missing data"}), 400

    try:
        cursor = mysql.connection.cursor()
        query = """
        INSERT INTO singleplayer_scores (user_id, category, score, time_taken, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (user_id, category, score, time_taken))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Score stored successfully!"}), 200
    except MySQLdb.Error as err:
        return jsonify({"error": str(err)}), 500

@app.route('/singleplayer_result')
def singleplayer_result():
    return render_template('singleplayer_result.html')


# ✅ Route: Serve HTML Pages
@app.route('/')
def home():
    return render_template("index.html")

@app.route('/multiplayer')
def multiplayer():
    return render_template("multi_choose.html")

@app.route('/multi_choose')
def multi_choose():
    return render_template("multi_choose.html")

@app.route('/multi_host')
def multi_host():
    return render_template("multi_host.html")

@app.route('/multi_join')
def multi_join():
    return render_template("multi_join.html")

@app.route('/multi_lobby')
def multi_lobby():
    return render_template("multi_lobby.html")



# ✅ Run Flask App
if __name__ == '__main__':
    app.run(debug=True)
