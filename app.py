import os, sys, sqlite3, secrets, shutil, csv, io, base64
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, abort, Response
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
# In a packaged EXE, persistent files must live OUTSIDE the temporary executable bundle.
if getattr(sys, 'frozen', False):
    USERDATA = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'RobarosiyaInventory'
else:
    USERDATA = Path(__file__).resolve().parent
DATA = USERDATA / 'data'; DATA.mkdir(parents=True, exist_ok=True)
BACKUPS = USERDATA / 'backups'; BACKUPS.mkdir(parents=True, exist_ok=True)
DB = DATA / 'inventory.db'
app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
# Embed the logo to keep it visible even when the browser cannot fetch /static assets.
LOGO_DATA_URL = "data:image/png;base64," + base64.b64encode((ROOT / "static" / "logo.png").read_bytes()).decode("ascii")
keyfile = DATA / '.secret_key'
if not keyfile.exists(): keyfile.write_text(secrets.token_hex(32), encoding='utf-8')
app.secret_key = keyfile.read_text(encoding='utf-8')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
DEPTS = ['Kitchen','Bar','Housekeeping','Maintenance','Other','Restaurant']
UNITS = ['pcs','kg','g','L','mL','bottles','packets','boxes','cans','rolls','sets']

def conn():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init_db():
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','staff')), active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'General', unit TEXT NOT NULL, min_qty REAL NOT NULL DEFAULT 0, price REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS batches (id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id), qty REAL NOT NULL CHECK(qty>=0), expiry TEXT, unit_cost REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id), batch_id INTEGER REFERENCES batches(id), kind TEXT NOT NULL CHECK(kind IN ('IN','OUT')), qty REAL NOT NULL CHECK(qty>0), unit_cost REAL NOT NULL DEFAULT 0, department TEXT, actor_id INTEGER REFERENCES users(id), created_at TEXT NOT NULL, note TEXT);
        CREATE TABLE IF NOT EXISTS fixed_assets (id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE, quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0), location TEXT NOT NULL DEFAULT 'General', updated_at TEXT NOT NULL, updated_by INTEGER REFERENCES users(id));
        CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(created_at);
        CREATE INDEX IF NOT EXISTS idx_batches_item ON batches(item_id);
        ''')
init_db()

def seed_fixed_assets():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with conn() as c:
        for name in ('Chairs', 'Plates'):
            c.execute('INSERT OR IGNORE INTO fixed_assets(name, quantity, location, updated_at) VALUES(?,?,?,?)', (name, 0, 'General', now))
seed_fixed_assets()

def q(sql, args=(), one=False):
    with conn() as c:
        rows = c.execute(sql,args).fetchall()
    return rows[0] if one and rows else (None if one else rows)

def csrf():
    if 'csrf' not in session: session['csrf'] = secrets.token_hex(24)
    return session['csrf']
app.jinja_env.globals['logo_data_url'] = LOGO_DATA_URL
app.jinja_env.globals['csrf_token'] = csrf
app.jinja_env.globals['today'] = lambda: date.today().isoformat()
app.jinja_env.globals['DEPTS'] = DEPTS
app.jinja_env.globals['UNITS'] = UNITS

@app.before_request
def protection():
    if request.method == 'POST':
        if not secrets.compare_digest(request.form.get('csrf_token',''), csrf()): abort(400, 'Invalid form token. Refresh page and try again.')
    if request.endpoint not in ('setup','static') and not q('SELECT id FROM users LIMIT 1',one=True):
        return redirect(url_for('setup'))

def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get('user_id'): return redirect(url_for('login'))
        user=q('SELECT * FROM users WHERE id=? AND active=1',(session['user_id'],),True)
        if not user: session.clear(); return redirect(url_for('login'))
        return fn(*a,**kw)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if session.get('role') != 'admin': abort(403)
        return fn(*a,**kw)
    return wrapper

@app.context_processor
def common(): return {'logged_user':session.get('username'), 'role':session.get('role')}

@app.route('/setup', methods=['GET','POST'])
def setup():
    if q('SELECT id FROM users LIMIT 1',one=True): return redirect(url_for('login'))
    if request.method == 'POST':
        name=request.form.get('username','').strip(); pw=request.form.get('password','')
        if len(name)<3 or len(pw)<8: flash('Username must have 3+ characters and password 8+ characters.','error')
        else:
            with conn() as c: c.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(name,generate_password_hash(pw),'admin'))
            flash('Admin created. Please log in.','success'); return redirect(url_for('login'))
    return render_template('auth.html',page='First-time Admin Setup')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=q('SELECT * FROM users WHERE username=? AND active=1',(request.form.get('username','').strip(),),True)
        if u and check_password_hash(u['password_hash'],request.form.get('password','')):
            session.clear(); session.update(user_id=u['id'],username=u['username'],role=u['role']); csrf()
            return redirect(url_for('dashboard'))
        flash('Incorrect username or password.','error')
    return render_template('auth.html',page='Sign In')

@app.route('/logout',methods=['POST'])
@login_required
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    summary=q('''SELECT count(*) items,coalesce(sum(qty),0) total_qty,coalesce(sum(qty*price),0) value, sum(CASE WHEN qty<=min_qty THEN 1 ELSE 0 END) low FROM (SELECT i.id,i.min_qty,i.price,coalesce(sum(b.qty),0) qty FROM items i LEFT JOIN batches b ON b.item_id=i.id WHERE i.active=1 GROUP BY i.id)''',one=True)
    exp=q('''SELECT i.name, b.qty, b.expiry FROM batches b JOIN items i ON i.id=b.item_id WHERE b.qty>0 AND b.expiry IS NOT NULL AND b.expiry<=? ORDER BY b.expiry LIMIT 12''',((date.today()+timedelta(days=30)).isoformat(),))
    low=q('''SELECT i.name,i.unit,i.min_qty,coalesce(sum(b.qty),0) qty FROM items i LEFT JOIN batches b ON b.item_id=i.id WHERE i.active=1 GROUP BY i.id HAVING qty<=i.min_qty ORDER BY qty LIMIT 12''')
    recent=q('''SELECT t.*,i.name,i.unit,u.username FROM transactions t JOIN items i ON i.id=t.item_id LEFT JOIN users u ON u.id=t.actor_id ORDER BY t.id DESC LIMIT 8''')
    assets=q('SELECT id,name,quantity,location FROM fixed_assets ORDER BY name')
    return render_template('dashboard.html',summary=summary,exp=exp,low=low,recent=recent,assets=assets)

@app.route('/fixed-assets', methods=['GET','POST'])
@login_required
def fixed_assets():
    if request.method == 'POST':
        if session.get('role') != 'admin': abort(403)
        name = request.form.get('name','').strip()
        location = request.form.get('location','General').strip() or 'General'
        try:
            qty_text=request.form.get('quantity','')
            if not qty_text.isdigit(): raise ValueError('Quantity must be a whole number (0 or more).')
            quantity=int(qty_text)
            if not name or len(name)>90 or len(location)>90 or quantity>100000000: raise ValueError('Check name, location and quantity.')
            with conn() as c:
                c.execute('INSERT INTO fixed_assets(name,quantity,location,updated_at,updated_by) VALUES(?,?,?,?,?)', (name,quantity,location,datetime.now().strftime('%Y-%m-%d %H:%M:%S'),session['user_id']))
            flash('Fixed asset added.','success')
        except (ValueError,sqlite3.IntegrityError) as e: flash('Cannot add asset: '+str(e),'error')
        return redirect(url_for('fixed_assets'))
    assets=q('SELECT a.*,u.username AS updated_user FROM fixed_assets a LEFT JOIN users u ON u.id=a.updated_by ORDER BY a.name')
    return render_template('fixed_assets.html',assets=assets)

@app.route('/fixed-assets/<int:asset_id>/update', methods=['POST'])
@admin_required
def update_fixed_asset(asset_id):
    try:
        name=request.form.get('name','').strip()
        location=request.form.get('location','General').strip() or 'General'
        qty_text=request.form.get('quantity','')
        if not qty_text.isdigit(): raise ValueError('Quantity must be a whole number (0 or more).')
        quantity=int(qty_text)
        if not name or len(name)>90 or len(location)>90 or quantity>100000000: raise ValueError('Check name, location and quantity.')
        with conn() as c:
            result=c.execute('UPDATE fixed_assets SET name=?,quantity=?,location=?,updated_at=?,updated_by=? WHERE id=?', (name,quantity,location,datetime.now().strftime('%Y-%m-%d %H:%M:%S'),session['user_id'],asset_id))
            if not result.rowcount: abort(404)
        flash('Fixed asset updated.','success')
    except (ValueError,sqlite3.IntegrityError) as e: flash('Cannot update asset: '+str(e),'error')
    return redirect(url_for('fixed_assets'))

@app.route('/fixed-assets/<int:asset_id>/delete', methods=['POST'])
@admin_required
def delete_fixed_asset(asset_id):
    with conn() as c: c.execute('DELETE FROM fixed_assets WHERE id=?',(asset_id,))
    flash('Fixed asset removed.','success')
    return redirect(url_for('fixed_assets'))

@app.route('/items',methods=['GET','POST'])
@login_required
def items():
    if request.method=='POST':
        if session['role']!='admin': abort(403)
        try:
            code=request.form['code'].strip().upper(); name=request.form['name'].strip(); category=request.form.get('category','General').strip() or 'General'; unit=request.form['unit']
            minimum=float(request.form.get('min_qty') or 0); price=float(request.form.get('price') or 0)
            if not code or not name or unit not in UNITS or minimum<0 or price<0: raise ValueError('Invalid item details')
            with conn() as c: c.execute('INSERT INTO items(code,name,category,unit,min_qty,price) VALUES(?,?,?,?,?,?)',(code,name,category,unit,minimum,price))
            flash('Item added.','success')
        except (ValueError,sqlite3.IntegrityError) as e: flash('Could not add item: '+str(e),'error')
        return redirect(url_for('items'))
    rows=q('''SELECT i.*, coalesce(sum(b.qty),0) qty FROM items i LEFT JOIN batches b ON b.item_id=i.id WHERE i.active=1 GROUP BY i.id ORDER BY i.name''')
    return render_template('items.html',items=rows)

@app.route('/items/<int:item_id>/edit',methods=['GET','POST'])
@admin_required
def edit_item(item_id):
    item=q('SELECT * FROM items WHERE id=? AND active=1',(item_id,),True)
    if not item: abort(404)
    if request.method=='POST':
        try:
            name=request.form['name'].strip(); category=request.form.get('category','General').strip() or 'General'; min_qty=float(request.form['min_qty']); price=float(request.form['price'])
            if not name or min_qty<0 or price<0: raise ValueError('Invalid values')
            with conn() as c: c.execute('UPDATE items SET name=?,category=?,min_qty=?,price=? WHERE id=?',(name,category,min_qty,price,item_id))
            flash('Item updated.','success'); return redirect(url_for('items'))
        except ValueError as e: flash(str(e),'error')
    return render_template('edit_item.html',item=item)

@app.route('/items/<int:item_id>/archive',methods=['POST'])
@admin_required
def archive_item(item_id):
    with conn() as c: c.execute('UPDATE items SET active=0 WHERE id=?',(item_id,))
    flash('Item archived; transaction history preserved.','success'); return redirect(url_for('items'))

@app.route('/stock/<kind>',methods=['GET','POST'])
@login_required
def stock(kind):
    if kind not in ('in','out'): abort(404)
    if request.method=='POST':
        try:
            item_id=int(request.form['item_id']); amount=float(request.form['qty']); department=request.form.get('department','') if kind=='out' else None
            if not (0<amount<1e9): raise ValueError('Quantity must be greater than zero.')
            if kind=='out' and department not in DEPTS: raise ValueError('Choose a valid department.')
            item=q('SELECT * FROM items WHERE id=? AND active=1',(item_id,),True)
            if not item: raise ValueError('Item not found.')
            now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with conn() as c:
                c.execute('BEGIN IMMEDIATE')
                if kind=='in':
                    expiry=request.form.get('expiry') or None
                    if expiry: date.fromisoformat(expiry)
                    cost=float(request.form.get('cost') or item['price'])
                    if cost<0: raise ValueError('Cost cannot be negative.')
                    cur=c.execute('INSERT INTO batches(item_id,qty,expiry,unit_cost,created_at) VALUES(?,?,?,?,?)',(item_id,amount,expiry,cost,now))
                    c.execute('INSERT INTO transactions(item_id,batch_id,kind,qty,unit_cost,actor_id,created_at,note) VALUES(?,?,?,?,?,?,?,?)',(item_id,cur.lastrowid,'IN',amount,cost,session['user_id'],now,request.form.get('note','')[:250]))
                    c.execute('UPDATE items SET price=? WHERE id=?',(cost,item_id))
                else:
                    batches=c.execute('''SELECT * FROM batches WHERE item_id=? AND qty>0 AND (expiry IS NULL OR expiry>=?) ORDER BY CASE WHEN expiry IS NULL THEN 1 ELSE 0 END, expiry, id''',(item_id,date.today().isoformat())).fetchall()
                    if sum(b['qty'] for b in batches)+1e-8 < amount: raise ValueError('Not enough unexpired stock. Check expired batches.')
                    remaining=amount
                    for b in batches:
                        used=min(remaining,b['qty'])
                        if used<=0: continue
                        c.execute('UPDATE batches SET qty=qty-? WHERE id=?',(used,b['id']))
                        c.execute('INSERT INTO transactions(item_id,batch_id,kind,qty,unit_cost,department,actor_id,created_at,note) VALUES(?,?,?,?,?,?,?,?,?)',(item_id,b['id'],'OUT',used,b['unit_cost'],department,session['user_id'],now,request.form.get('note','')[:250]))
                        remaining-=used
                        if remaining<1e-8: break
            flash('Stock '+kind.upper()+' saved successfully.','success'); return redirect(url_for('stock',kind=kind))
        except (ValueError,sqlite3.Error,KeyError) as e: flash('Stock not saved: '+str(e),'error')
    rows=q('''SELECT i.id,i.name,i.code,i.unit,i.price,coalesce(sum(b.qty),0) qty FROM items i LEFT JOIN batches b ON b.item_id=i.id WHERE i.active=1 GROUP BY i.id ORDER BY i.name''')
    return render_template('stock.html',kind=kind,items=rows)

@app.route('/reports')
@login_required
def reports():
    period=request.args.get('period','daily'); period=period if period in ('daily','monthly','all') else 'daily'
    start=date.today().isoformat() if period=='daily' else date.today().replace(day=1).isoformat() if period=='monthly' else '0001-01-01'
    rows=q('''SELECT t.created_at,t.kind,i.code,i.name,i.unit,t.qty,t.unit_cost,t.department,u.username,t.note FROM transactions t JOIN items i ON i.id=t.item_id LEFT JOIN users u ON u.id=t.actor_id WHERE t.created_at>=? ORDER BY t.id DESC LIMIT 3000''',(start,))
    usage=q('''SELECT department, i.name,i.unit,round(sum(t.qty),3) qty,round(sum(t.qty*t.unit_cost),2) cost FROM transactions t JOIN items i ON i.id=t.item_id WHERE t.kind='OUT' AND t.created_at>=? GROUP BY department,i.id ORDER BY department,i.name''',(start,))
    if request.args.get('export')=='csv':
        out=io.StringIO(); writer=csv.writer(out); writer.writerow(['Date','Type','Code','Item','Unit','Quantity','Unit Cost (LKR)','Department','User','Note'])
        for r in rows: writer.writerow(list(r))
        return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename=Robarosiya_{period}_report.csv'})
    return render_template('reports.html',period=period,rows=rows,usage=usage)

@app.route('/staff',methods=['GET','POST'])
@admin_required
def staff():
    if request.method=='POST':
        name=request.form.get('username','').strip(); password=request.form.get('password','')
        if len(name)<3 or len(password)<8: flash('Username 3+ chars and password 8+ chars required.','error')
        else:
            try:
                with conn() as c: c.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(name,generate_password_hash(password),'staff'))
                flash('Staff account added.','success')
            except sqlite3.IntegrityError: flash('Username already used.','error')
        return redirect(url_for('staff'))
    users=q('SELECT id,username,role,active FROM users ORDER BY id')
    return render_template('staff.html',users=users)

@app.route('/staff/<int:uid>/toggle',methods=['POST'])
@admin_required
def toggle_staff(uid):
    with conn() as c: c.execute("UPDATE users SET active=1-active WHERE id=? AND role='staff'",(uid,))
    return redirect(url_for('staff'))

@app.route('/backup',methods=['POST'])
@admin_required
def backup():
    backup_path=BACKUPS / ('inventory_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.db')
    source=conn()
    try:
        destination=sqlite3.connect(backup_path)
        try: source.backup(destination)
        finally: destination.close()
    finally: source.close()
    return send_file(backup_path,as_attachment=True,download_name=backup_path.name)

@app.errorhandler(403)
def forbidden(e): return render_template('error.html',message='You do not have permission to access this page.'),403
@app.errorhandler(404)
def missing(e): return render_template('error.html',message='Page not found.'),404

if __name__=='__main__':
    from werkzeug.serving import make_server
    import webbrowser, threading
    server=make_server('127.0.0.1',5000,app)
    threading.Timer(1.5, lambda:webbrowser.open('http://127.0.0.1:5000')).start()
    print('Robarosiya Inventory running at http://127.0.0.1:5000')
    server.serve_forever()
