
@app.route('/save-list', methods=['POST'])
def save_list():
    words_json = request.form.get('words_json')
    if not words_json:
        return 'No data provided', 400

    try:
        words = json.loads(words_json)
        for item in words:
            new_word = Word(
                word=item.get('word'),
                meaning=item.get('meaning'),
                user_id=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(new_word)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return f"Error saving words: {e}", 500

    return redirect(url_for('word_list'))
