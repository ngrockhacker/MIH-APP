from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from datetime import datetime, timedelta
import sqlite3
import random
from motivational_quotes import quotes_list
from task_list import daily_tasks
from werkzeug.user_agent import UserAgent

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure Flask-Mail settings

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['id'])
    return None

def get_db_connection():
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    with get_db_connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS notes (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date TEXT NOT NULL,
                            note_type TEXT,
                            note_content TEXT,
                            user_id INTEGER,
                            FOREIGN KEY (user_id) REFERENCES users (id))''')
        conn.execute('''CREATE TABLE IF NOT EXISTS daily_tasks (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            date TEXT NOT NULL,
                            task_completed BOOLEAN DEFAULT FALSE,
                            FOREIGN KEY (user_id) REFERENCES users (id))''')
        conn.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            user_obj = User(user['id'])
            login_user(user_obj)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))

    # Add the provided code to detect if the user is using a mobile device
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent
    
    if is_mobile:
        return render_template('login_mobile.html', login_mobile=True)
    else:
        return render_template('login.html', login=True)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/get_random_quote')
@login_required
def get_random_quote():
    if 'last_quote_time' in session:
        last_quote_time = session['last_quote_time']
        now = datetime.now().astimezone()  # Make it offset-aware
        if now - last_quote_time < timedelta(days=1):
            return jsonify(session['last_quote'])

    quote = random.choice(quotes_list)
    session['last_quote'] = {'quote': quote, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    session['last_quote_time'] = datetime.now().astimezone()  # Store an offset-aware datetime
    return jsonify(quote=quote)


@app.route('/')
@login_required
def home():
    notes_count = {}
    conn = get_db_connection()
    notes_cursor = conn.execute('SELECT date, COUNT(*) FROM notes WHERE user_id = ? GROUP BY date', (current_user.id,)).fetchall()
    conn.close()
    for note in notes_cursor:
        notes_count[note['date']] = note['COUNT(*)']
    
    # Determine if the request is from a mobile device
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent
    
    if is_mobile:
        return render_template('index_mobile.html', notes_count=notes_count)
    else:
        return render_template('index.html', notes_count=notes_count)

@app.route('/dashboard')
@login_required
def dashboard():
    # Determine if the request is from a mobile device
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent
    
    if is_mobile:
        print("MOBILE")
        return render_template('dashboard_mobile.html')
    else:
        return render_template('dashboard.html')

from flask import request

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        with get_db_connection() as conn:
            if conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone() is None:
                conn.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)', 
                             (username, password, email))
                conn.commit()
                return redirect(url_for('login'))
            else:
                flash('Username or email already exists', 'error')
                return redirect(url_for('signup'))
    
    if is_mobile:
        return render_template('signup_mobile.html')
    else:
        return render_template('signup.html')


@app.route('/notes/<date>')
@login_required
def notes(date):
    conn = get_db_connection()
    task_info = conn.execute('SELECT task_completed FROM daily_tasks WHERE user_id = ? AND date = ?', (current_user.id, date)).fetchone()
    daily_task_completed = task_info['task_completed'] if task_info else False
    notes_cursor = conn.execute('SELECT * FROM notes WHERE date = ? AND user_id = ?', (date, current_user.id)).fetchall()
    conn.close()
    notes = [{'type': note['note_type'], 'content': note['note_content']} for note in notes_cursor]
    daily_task = daily_tasks.get(datetime.strptime(date, '%Y-%m-%d').weekday(), "No specific task for today.")
    
    # Determine if the request is from a mobile device
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent
    
    if is_mobile:
        return render_template('notes_mobile.html', date=date, notes=notes, daily_task=daily_task, daily_task_completed=daily_task_completed)
    else:
        return render_template('notes.html', date=date, notes=notes, daily_task=daily_task, daily_task_completed=daily_task_completed)

@app.route('/save_note', methods=['POST'])
@login_required
def save_note():
    date = request.form['date']
    note_type = request.form.get('note_type')
    note_content = request.form['note']
    user_id = current_user.id
    with get_db_connection() as conn:
        conn.execute('INSERT INTO notes (date, note_type, note_content, user_id) VALUES (?, ?, ?, ?)', 
                     (date, note_type, note_content, user_id))
        conn.commit()
    return jsonify(success=True)

@app.route('/save_daily_task_state', methods=['POST'])
@login_required
def save_daily_task_state():
    completed = request.form.get('daily_task_completed') == 'true'
    date = request.form.get('date')
    with get_db_connection() as conn:
        existing = conn.execute('SELECT id FROM daily_tasks WHERE user_id = ? AND date = ?', (current_user.id, date)).fetchone()
        if existing:
            conn.execute('UPDATE daily_tasks SET task_completed = ? WHERE id = ?', (completed, existing['id']))
        else:
            conn.execute('INSERT INTO daily_tasks (user_id, date, task_completed) VALUES (?, ?, ?)', (current_user.id, date, completed))
        conn.commit()
    return jsonify(success=True)

@app.route('/delete_note', methods=['POST'])
@login_required
def delete_note():
    note_type = request.form['note_type']
    with get_db_connection() as conn:
        conn.execute('DELETE FROM notes WHERE note_type = ? AND user_id = ?', (note_type, current_user.id))
        conn.commit()
    return jsonify(success=True)

@app.route('/edit_note', methods=['POST'])
@login_required
def edit_note():
    note_type = request.form['note_type']
    new_content = request.form['new_content']
    with get_db_connection() as conn:
        conn.execute('UPDATE notes SET note_content = ? WHERE note_type = ? AND user_id = ?', 
                     (new_content, note_type, current_user.id))
        conn.commit()
    return jsonify(success=True)


@app.route('/dashboard_data')
@login_required
def dashboard_data():
    conn = get_db_connection()
    notes_30_days = conn.execute('''SELECT date, COUNT(*) as count FROM notes 
                                    WHERE user_id = ? AND date >= DATE('now', '-30 days') 
                                    GROUP BY date''', (current_user.id,)).fetchall()
    notes_year_avg = conn.execute('''SELECT strftime('%m', date) as month, COUNT(*) as count FROM notes 
                                     WHERE user_id = ? AND date >= DATE('now', '-1 year') 
                                     GROUP BY strftime('%m', date)''', (current_user.id,)).fetchall()
    notes_year_avg = {note['month']: note['count']/12.0 for note in notes_year_avg}
    completed_tasks_30_days = conn.execute('''SELECT COUNT(*) FROM daily_tasks 
                                              WHERE user_id = ? AND date >= DATE('now', '-30 days') 
                                              AND task_completed = 1''', 
                                              (current_user.id,)).fetchone()[0]
    completion_rate_30_days = (completed_tasks_30_days / 30) * 100
    completed_tasks_year = conn.execute('''SELECT COUNT(*) FROM daily_tasks 
                                           WHERE user_id = ? AND date >= DATE('now', '-1 year') 
                                           AND task_completed = 1''', 
                                           (current_user.id,)).fetchone()[0]
    completion_rate_year = (completed_tasks_year / 365) * 100
    conn.close()
    data = {
        'notes_30_days': {note['date']: note['count'] for note in notes_30_days},
        'notes_year_avg': notes_year_avg,
        'completion_rate_30_days': completion_rate_30_days,
        'completion_rate_year': completion_rate_year,
    }
    return jsonify(data)

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True, host='0.0.0.0')
