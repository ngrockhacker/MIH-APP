from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from datetime import datetime, timedelta
import psycopg2
import random
from motivational_quotes import quotes_list
from task_list import daily_tasks

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
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    conn.close()
    if user:
        return User(user[0])
    return None

def get_db_connection():
    conn = psycopg2.connect(
        "postgres://default:LAGs5tiXV6MS@ep-holy-butterfly-a7dm7y2d.ap-southeast-2.aws.neon.tech:5432/verceldb?sslmode=require"
    )
    return conn

def initialize_database():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS notes (
                            id SERIAL PRIMARY KEY,
                            date TEXT NOT NULL,
                            note_type TEXT,
                            note_content TEXT,
                            user_id INTEGER,
                            FOREIGN KEY (user_id) REFERENCES users (id))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS daily_tasks (
                            id SERIAL PRIMARY KEY,
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
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cur.fetchone()
        conn.close()
        if user:
            user_obj = User(user[0])
            login_user(user_obj)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))

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
        now = datetime.now().astimezone()
        if now - last_quote_time < timedelta(days=1):
            return jsonify(session['last_quote'])

    quote = random.choice(quotes_list)
    session['last_quote'] = {'quote': quote, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    session['last_quote_time'] = datetime.now().astimezone()
    return jsonify(quote=quote)

@app.route('/')
@login_required
def home():
    notes_count = {}
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT date, COUNT(*) FROM notes WHERE user_id = %s GROUP BY date', (current_user.id,))
    notes_cursor = cur.fetchall()
    conn.close()
    for note in notes_cursor:
        notes_count[note[0]] = note[1]
    
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent
    
    if is_mobile:
        return render_template('index_mobile.html', notes_count=notes_count)
    else:
        return render_template('index.html', notes_count=notes_count)

@app.route('/dashboard')
@login_required
def dashboard():
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent
    
    if is_mobile:
        return render_template('dashboard_mobile.html')
    else:
        return render_template('dashboard.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM users WHERE username = %s OR email = %s', (username, email))
            if cur.fetchone() is None:
                cur.execute('INSERT INTO users (username, password, email) VALUES (%s, %s, %s)', 
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
    cur = conn.cursor()
    cur.execute('SELECT task_completed FROM daily_tasks WHERE user_id = %s AND date = %s', (current_user.id, date))
    task_info = cur.fetchone()
    daily_task_completed = task_info[0] if task_info else False
    cur.execute('SELECT * FROM notes WHERE date = %s AND user_id = %s', (date, current_user.id))
    notes_cursor = cur.fetchall()
    conn.close()
    notes = [{'type': note[2], 'content': note[3]} for note in notes_cursor]
    daily_task = daily_tasks.get(datetime.strptime(date, '%Y-%m-%d').weekday(), "No specific task for today.")
    
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
        cur = conn.cursor()
        cur.execute('INSERT INTO notes (date, note_type, note_content, user_id) VALUES (%s, %s, %s, %s)', 
                    (date, note_type, note_content, user_id))
        conn.commit()
    return jsonify(success=True)

@app.route('/save_daily_task_state', methods=['POST'])
@login_required
def save_daily_task_state():
    completed = request.form.get('daily_task_completed') == 'true'
    date = request.form.get('date')
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT id FROM daily_tasks WHERE user_id = %s AND date = %s', (current_user.id, date))
        existing = cur.fetchone()
        if existing:
            cur.execute('UPDATE daily_tasks SET task_completed = %s WHERE id = %s', (completed, existing[0]))
        else:
            cur.execute('INSERT INTO daily_tasks (user_id, date, task_completed) VALUES (%s, %s, %s)', (current_user.id, date, completed))
        conn.commit()
    return jsonify(success=True)

@app.route('/delete_note', methods=['POST'])
@login_required
def delete_note():
    note_type = request.form['note_type']
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute('DELETE FROM notes WHERE note_type = %s AND user_id = %s', (note_type, current_user.id))
        conn.commit()
    return jsonify(success=True)

@app.route('/edit_note', methods=['POST'])
@login_required
def edit_note():
    note_type = request.form['note_type']
    new_content = request.form['new_content']
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE notes SET note_content = %s WHERE note_type = %s AND user_id = %s', 
                    (new_content, note_type, current_user.id))
        conn.commit()
    return jsonify(success=True)

@app.route('/dashboard_data')
@login_required
def dashboard_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''SELECT date, COUNT(*) as count FROM notes 
                   WHERE user_id = %s AND date >= (CURRENT_DATE - INTERVAL '30 days')
                   GROUP BY date''', (current_user.id,))
    notes_30_days = cur.fetchall()
    cur.execute('''SELECT TO_CHAR(date, 'MM') as month, COUNT(*) as count FROM notes 
                   WHERE user_id = %s AND date >= (CURRENT_DATE - INTERVAL '1 year')
                   GROUP BY TO_CHAR(date, 'MM')''', (current_user.id,))
    notes_year_avg = cur.fetchall()
    notes_year_avg = {note[0]: note[1]/12.0 for note in notes_year_avg}
    cur.execute('''SELECT COUNT(*) FROM daily_tasks 
                   WHERE user_id = %s AND date >= (CURRENT_DATE - INTERVAL '30 days')
                   AND task_completed = TRUE''', 
                   (current_user.id,))
    completed_tasks_30_days = cur.fetchone()[0]
    completion_rate_30_days = (completed_tasks_30_days / 30) * 100
    cur.execute('''SELECT COUNT(*) FROM daily_tasks 
                   WHERE user_id = %s AND date >= (CURRENT_DATE - INTERVAL '1 year')
                   AND task_completed = TRUE''', 
                   (current_user.id,))
    completed_tasks_year = cur.fetchone()[0]
    completion_rate_year = (completed_tasks_year / 365) * 100
    conn.close()
    data = {
        'notes_30_days': {note[0]: note[1] for note in notes_30_days},
        'notes_year_avg': notes_year_avg,
        'completion_rate_30_days': completion_rate_30_days,
        'completion_rate_year': completion_rate_year,
    }
    return jsonify(data)

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True, host='0.0.0.0')
