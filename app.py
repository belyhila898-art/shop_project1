from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'super-secret-key-change-in-production'
DB_NAME = 'db.sqlite3'

# --- Инициализация БД ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','manager','admin'))
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                discount INTEGER DEFAULT 0,
                image_url TEXT,
                category TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT DEFAULT 'new',
                total_price INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        c.execute('SELECT count(*) FROM users')
        if c.fetchone()[0] == 0:
            c.executemany('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', [
                ('admin', 'admin123', 'admin'),
                ('manager', 'manager123', 'manager'),
                ('user', 'user123', 'user')
            ])
            test_products = [
                ('Ноутбук игровой', 'RTX 4060, i5-13500H', 99900, 0, 'https://via.placeholder.com/300x200?text=Laptop', 'electronics'),
                ('Смартфон флагман', '128 ГБ, камера 50 МП', 49900, 5000, 'https://via.placeholder.com/300x200?text=Phone', 'electronics'),
                ('Наушники беспроводные', 'Шумоподавление', 12900, 2000, 'https://via.placeholder.com/300x200?text=Headphones', 'electronics'),
                ('Футболка базовая', 'Хлопок 100%', 1990, 300, 'https://via.placeholder.com/300x200?text=TShirt', 'clothing'),
                ('Джинсы классические', 'Прямой крой', 4990, 1000, 'https://via.placeholder.com/300x200?text=Jeans', 'clothing'),
                ('Диван прямой', 'Ткань рогожка, спальное место', 29900, 5000, 'https://via.placeholder.com/300x200?text=Sofa', 'furniture'),
                ('Кресло офисное', 'Регулировка высоты', 14900, 2000, 'https://via.placeholder.com/300x200?text=Chair', 'furniture'),
            ]
            c.executemany('''
                INSERT INTO products (name, description, price, discount, image_url, category)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', test_products)

init_db()

# --- Декораторы ---
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def role_required(*roles):
    def decorator(f):
        def wrapper(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash('У вас нет доступа к этой странице', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# --- Маршруты ---
@app.route('/')
def index():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM products ORDER BY id LIMIT 20')
        products = cur.fetchall()
    return render_template('index.html', products=products)

@app.route('/catalog')
@app.route('/catalog/<cat>')
def catalog(cat='all'):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if cat == 'all':
            cur.execute('SELECT * FROM products')
        else:
            cur.execute('SELECT * FROM products WHERE category = ?', (cat,))
        products = cur.fetchall()
        category = cat
    return render_template('catalog.html', products=products, category=category)

@app.route('/product/<int:pid>')
def product(pid):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM products WHERE id = ?', (pid,))
        product = cur.fetchone()
    if not product:
        flash('Товар не найден', 'error')
        return redirect(url_for('catalog'))
    return render_template('product.html', product=product)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
            user = cur.fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Вы вошли в систему', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))

@app.route('/cart', methods=['GET', 'POST'])
@login_required
def cart():
    if request.method == 'POST':
        pid = request.form.get('pid')
        qty = request.form.get('qty', 1)
        action = request.form.get('add')
        remove = request.form.get('remove')
        checkout = request.form.get('checkout')

        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            if action:
                cur.execute(
                    'INSERT OR REPLACE INTO cart (user_id, product_id, quantity) VALUES (?, ?, COALESCE((SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?) + ?, 1))',
                    (session['user_id'], pid, session['user_id'], pid, qty)
                )
                flash('Товар добавлен в корзину', 'success')
            elif remove:
                cid = request.form.get('cid')
                cur.execute('DELETE FROM cart WHERE id = ?', (cid,))
                flash('Товар удалён из корзины', 'success')
            elif checkout:
                cur.execute(
                    'SELECT p.price, p.discount, c.quantity FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id = ?',
                    (session['user_id'],)
                )
                items = cur.fetchall()
                total = sum((row[0] - row[1]) * row[2] for row in items)
                if total > 0:
                    cur.execute('INSERT INTO orders (user_id, total_price) VALUES (?, ?)', (session['user_id'], total))
                    cur.execute('DELETE FROM cart WHERE user_id = ?', (session['user_id'],))
                    flash(f'Заказ оформлен на сумму {total} ₽', 'success')
                else:
                    flash('Корзина пуста', 'error')

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('''
            SELECT c.id AS cart_id, p.*, c.quantity
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
        ''', (session['user_id'],))
        items = cur.fetchall()

    return render_template('cart.html', items=items)

@app.route('/dashboard_admin', methods=['GET', 'POST'])
@role_required('admin')
def dashboard_admin():
    if request.method == 'POST':
        if request.form.get('add_product'):
            name = request.form['name']
            category = request.form['category']
            desc = request.form['desc']
            price = int(request.form['price'])
            discount = int(request.form.get('discount', 0))
            img = request.form['img']
            with sqlite3.connect(DB_NAME) as conn:
                cur = conn.cursor()
                cur.execute(
                    'INSERT INTO products (name, description, price, discount, image_url, category) VALUES (?, ?, ?, ?, ?, ?)',
                    (name, desc, price, discount, img, category)
                )
                flash('Товар добавлен', 'success')
            return redirect(url_for('dashboard_admin'))

        if 'delete_product' in request.form:
            pid = request.form['pid']
            with sqlite3.connect(DB_NAME) as conn:
                cur = conn.cursor()
                cur.execute('DELETE FROM products WHERE id = ?', (pid,))
                flash('Товар удалён', 'success')
            return redirect(url_for('dashboard_admin'))

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) AS total_orders, COALESCE(SUM(total_price), 0) AS total_revenue FROM orders')
        stats = cur.fetchone()
        cur.execute('SELECT * FROM products')
        products = cur.fetchall()

    return render_template('dashboard_admin.html', stats=stats, products=products)

@app.route('/dashboard_manager', methods=['GET', 'POST'])
@role_required('manager', 'admin')
def dashboard_manager():
    if request.method == 'POST' and request.form.get('add_product'):
        name = request.form['name']
        category = request.form['category']
        desc = request.form['desc']
        price = int(request.form['price'])
        discount = int(request.form.get('discount', 0))
        img = request.form['img']
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO products (name, description, price, discount, image_url, category) VALUES (?, ?, ?, ?, ?, ?)',
                (name, desc, price, discount, img, category)
            )
            flash('Товар добавлен', 'success')
        return redirect(url_for('dashboard_manager'))

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM products')
        products = cur.fetchall()

    return render_template('dashboard_manager.html', products=products)

@app.route('/edit_product/<int:pid>', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def edit_product(pid):
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        desc = request.form['desc']
        price = int(request.form['price'])
        discount = int(request.form.get('discount', 0))
        img = request.form['img']
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute('''
                UPDATE products
                SET name=?, description=?, price=?, discount=?, image_url=?, category=?
                WHERE id=?
            ''', (name, desc, price, discount, img, category, pid))
            flash('Товар обновлён', 'success')
        return redirect(url_for('dashboard_admin' if session['role'] == 'admin' else 'dashboard_manager'))

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM products WHERE id = ?', (pid,))
        product = cur.fetchone()

    if not product:
        flash('Товар не найден', 'error')
        return redirect(url_for('index'))

    return render_template('edit_product.html', product=product)

if __name__ == '__main__':
    app.run(host='192.168.56.1', port=5000, debug=True)
