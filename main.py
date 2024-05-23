from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from datetime import datetime, timedelta
import asyncpg
import random
from motivational_quotes import quotes_list
from task_list import daily_tasks

app = Flask(__name__)
app.secret_key = 'your_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
async def load_user(user_id):
    conn = await get_db_connection()
    user = await conn.fetchrow('SELECT * FROM users WHERE id = $1', user_id)
    await conn.close()
    if user:
        return User(user['id'])
    return None

async def get_db_connection():
    conn = await asyncpg.connect("postgres://default:LAGs5tiXV6MS@ep-holy-butterfly-a7dm7y2d.ap-southeast-2.aws.neon.tech:5432/verceldb?sslmode=require")
    return conn

async def initialize_database():
    conn = await get_db_connection()
    await conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE)''')
    await conn.execute('''CREATE TABLE IF NOT EXISTS notes (
                            id SERIAL PRIMARY KEY,
                            date TEXT NOT NULL,
                            note_type TEXT,
                            note_content TEXT,
                            user_id INTEGER,
                            FOREIGN KEY (user_id) REFERENCES users (id))''')
    await conn.execute('''CREATE TABLE IF NOT EXISTS daily_tasks (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER,
                            date TEXT NOT NULL,
                            task_completed BOOLEAN DEFAULT FALSE,
                            FOREIGN KEY (user_id) REFERENCES users (id))''')
    await conn.close()

@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = await get_db_connection()
        user = await conn.fetchrow('SELECT * FROM users WHERE username = $1 AND password = $2', username, password)
        await conn.close()
        if user:
            user_obj = User(user['id'])
            await login_user(user_obj)
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
async def logout():
    await logout_user()
    return redirect(url_for('login'))

@app.route('/get_random_quote')
@login_required
async def get_random_quote():
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
async def home():
    notes_count = {}
    conn = await get_db_connection()
    notes_cursor = await conn.fetch('SELECT date, COUNT(*) FROM notes WHERE user_id = $1 GROUP BY date', current_user.id)
    await conn.close()
    for note in notes_cursor:
        notes_count[note['date']] = note['count']

    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent

    if is_mobile:
        return render_template('index_mobile.html', notes_count=notes_count)
    else:
        return render_template('index.html', notes_count=notes_count)

@app.route('/dashboard')
@login_required
async def dashboard():
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent

    if is_mobile:
        return render_template('dashboard_mobile.html')
    else:
        return render_template('dashboard.html')

@app.route('/signup', methods=['GET', 'POST'])
async def signup():
    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        conn = await get_db_connection()
        existing_user = await conn.fetchrow('SELECT * FROM users WHERE username = $1 OR email = $2', username, email)
        if existing_user is None:
            await conn.execute('INSERT INTO users (username, password, email) VALUES ($1, $2, $3)', 
                               username, password, email)
            await conn.close()
            return redirect(url_for('login'))
        else:
            await conn.close()
            flash('Username or email already exists', 'error')
            return redirect(url_for('signup'))

    if is_mobile:
        return render_template('signup_mobile.html')
    else:
        return render_template('signup.html')

@app.route('/notes/<date>')
@login_required
async def notes(date):
    conn = await get_db_connection()
    task_info = await conn.fetchrow('SELECT task_completed FROM daily_tasks WHERE user_id = $1 AND date = $2', current_user.id, date)
    daily_task_completed = task_info['task_completed'] if task_info else False
    notes_cursor = await conn.fetch('SELECT * FROM notes WHERE date = $1 AND user_id = $2', date, current_user.id)
    await conn.close()
    notes = [{'type': note['note_type'], 'content': note['note_content']} for note in notes_cursor]
    daily_task = daily_tasks.get(datetime.strptime(date, '%Y-%m-%d').weekday(), "No specific task for today.")

    user_agent = request.user_agent.string
    is_mobile = 'iPhone' in user_agent or 'Android' in user_agent

    if is_mobile:
        return render_template('notes_mobile.html', date=date, notes=notes, daily_task=daily_task, daily_task_completed=daily_task_completed)
    else:
        return render_template('notes.html', date=date, notes=notes, daily_task=daily_task, daily_task_completed=daily_task_completed)

@app.route('/save_note', methods=['POST'])
@login_required
async def save_note():
    date = request.form['date']
    note_type = request.form.get('note_type')
    note_content = request.form['note']
    user_id = current_user.id
    conn = await get_db_connection()
    await conn.execute('INSERT INTO notes (date, note_type, note_content, user_id) VALUES ($1, $2, $3, $4)', 
                       date, note_type, note_content, user_id)
    await conn.close()
    return jsonify(success=True)

@app.route('/save_daily_task_state', methods=['POST'])
@login_required
async def save_daily_task_state():
    completed = request.form.get('daily_task_completed') == 'true'
    date = request.form.get('date')
    conn = await get_db_connection()
    existing = await conn.fetchrow('SELECT id FROM daily_tasks WHERE user_id = $1 AND date = $2', current_user.id, date)
    if existing:
        await conn.execute('UPDATE daily_tasks SET task_completed = $1 WHERE id = $2', completed, existing['id'])
    else:
        await conn.execute('INSERT INTO daily_tasks (user_id, date, task_completed) VALUES ($1, $2, $3)', current_user.id, date, completed)
    await conn.close()
    return jsonify(success=True)

@app.route('/delete_note', methods=['POST'])
@login_required
async def delete_note():
    note_type = request.form['note_type']
    conn = await get_db_connection()
    await conn.execute('DELETE FROM notes WHERE note_type = $1 AND user_id = $2', note_type, current_user.id)
    await conn.close()
    return jsonify(success=True)

@app.route('/edit_note', methods=['POST'])
@login_required
async def edit_note():
    note_type = request.form['note_type']
    new_content = request.form['new_content']
    conn = await get_db_connection()
    await conn.execute('UPDATE notes SET note_content = $1 WHERE note_type = $2 AND user_id = $3', 
                       new_content, note_type, current_user.id)
    await conn.close()
    return jsonify(success=True)

@app.route('/dashboard_data')
@login_required
async def dashboard_data():
    conn = await get_db_connection()
    notes_30_days = await conn.fetch('''SELECT date, COUNT(*) as count FROM notes 
                                        WHERE user_id = $1 AND date >= (CURRENT_DATE - INTERVAL '30 days') 
                                        GROUP BY date''', current_user.id)
    notes_year_avg = await conn.fetch('''SELECT EXTRACT(MONTH FROM date) as month, COUNT(*) as count FROM notes 
                                         WHERE user_id = $1 AND date >= (CURRENT_DATE - INTERVAL '1 year') 
                                         GROUP BY EXTRACT(MONTH FROM date)''', current_user.id)
    notes_year_avg = {note['month']: note['count'] / 12.0 for note in notes_year_avg}
    completed_tasks_30_days = await conn.fetchval('''SELECT COUNT(*) FROM daily_tasks 
                                                     WHERE user_id = $1 AND date >= (CURRENT_DATE - INTERVAL '30 days') 
                                                     AND task_completed = TRUE''', 
                                                     current_user.id)
    completion_rate_30_days = (completed_tasks_30_days / 30) * 100
    completed_tasks_year = await conn.fetchval('''SELECT COUNT(*) FROM daily_tasks 
                                                  WHERE user_id = $1 AND date >= (CURRENT_DATE - INTERVAL '1 year') 
                                                  AND task_completed = TRUE''', 
                                                  current_user.id)
    completion_rate_year = (completed_tasks_year / 365) * 100
    await conn.close()
    data = {
        'notes_30_days': {note['date']: note['count'] for note in notes_30_days},
        'notes_year_avg': notes_year_avg,
        'completion_rate_30_days': completion_rate_30_days,
        'completion_rate_year': completion_rate_year,
    }
    return jsonify(data)

if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(initialize_database())
    app.run(debug=True)
