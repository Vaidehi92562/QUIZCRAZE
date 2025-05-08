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

