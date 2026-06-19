from flask import Flask, render_template, request, jsonify, send_file
import sqlite3, analytics, io, os

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'cashcompas.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        type TEXT NOT NULL,
        category TEXT DEFAULT 'Others',
        note TEXT DEFAULT '',
        ai_tagged INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT UNIQUE NOT NULL,
        limit_amount REAL NOT NULL
    )''')
    # Seed data
    if conn.execute('SELECT COUNT(*) FROM transactions').fetchone()[0] == 0:
        seed_tx = [
            ('2026-06-15','Swiggy dinner order',480,'debit','Food & Dining','',1),
            ('2026-06-14','Amazon electronics order',4200,'debit','Shopping','',1),
            ('2026-06-13','Electricity bill payment',1800,'debit','Bills & Utilities','',1),
            ('2026-06-12','Uber ride to office',320,'debit','Travel','',1),
            ('2026-06-12','Netflix subscription',649,'debit','Entertainment','',1),
            ('2026-06-11','Zomato lunch',350,'debit','Food & Dining','',1),
            ('2026-06-10','Myntra clothes',2200,'debit','Shopping','',1),
            ('2026-06-09','Groww SIP investment',5000,'debit','Investments','Monthly SIP',0),
            ('2026-06-08','Apollo pharmacy',890,'debit','Healthcare','',1),
            ('2026-06-07','IRCTC train booking',1200,'debit','Travel','',1),
            ('2026-06-06','Udemy Python course',499,'debit','Education','',1),
            ('2026-06-05','Swiggy Instamart grocery',760,'debit','Food & Dining','',1),
            ('2026-06-04','Internet bill Jio',999,'debit','Bills & Utilities','',1),
            ('2026-06-03','Movie tickets PVR',640,'debit','Entertainment','',1),
            ('2026-06-01','Salary credit',82000,'credit','Others','June salary',0),
            ('2026-06-01','Freelance project payment',3000,'credit','Others','',0),
            ('2026-05-01','Salary credit',82000,'credit','Others','May salary',0),
            ('2026-05-15','Rent payment',15000,'debit','Bills & Utilities','',0),
            ('2026-05-10','Flipkart order',3500,'debit','Shopping','',1),
            ('2026-04-01','Salary credit',85000,'credit','Others','April salary',0),
            ('2026-04-22','Zerodha stocks',10000,'debit','Investments','',1),
            ('2026-04-10','Amazon gadgets',6200,'debit','Shopping','',1),
        ]
        conn.executemany(
            'INSERT INTO transactions (date,description,amount,type,category,note,ai_tagged) VALUES (?,?,?,?,?,?,?)',
            seed_tx
        )
    if conn.execute('SELECT COUNT(*) FROM budgets').fetchone()[0] == 0:
        conn.executemany('INSERT INTO budgets (category,limit_amount) VALUES (?,?)', [
            ('Food & Dining',12000),('Shopping',8000),('Bills & Utilities',6000),
            ('Travel',5000),('Entertainment',3000),('Investments',6000),
        ])
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/charts')
def charts_page():
    return render_template('charts.html')

# --- TRANSACTIONS ---
@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    conn = get_db()
    rows = conn.execute('SELECT * FROM transactions ORDER BY date DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    data = request.json
    conn = get_db()
    conn.execute(
        'INSERT INTO transactions (date,description,amount,type,category,note,ai_tagged) VALUES (?,?,?,?,?,?,?)',
        (data['date'], data['description'], float(data['amount']),
         data['type'], data['category'], data.get('note',''), data.get('ai_tagged',0))
    )
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    conn = get_db()
    conn.execute('DELETE FROM transactions WHERE id=?', (tx_id,))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/transactions/<int:tx_id>/category', methods=['PATCH'])
def update_category(tx_id):
    data = request.json
    conn = get_db()
    conn.execute('UPDATE transactions SET category=?,ai_tagged=0 WHERE id=?', (data['category'],tx_id))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

# --- BUDGETS ---
@app.route('/api/budgets', methods=['GET'])
def get_budgets():
    conn = get_db()
    budgets = conn.execute('SELECT * FROM budgets').fetchall()
    spent_rows = conn.execute(
        "SELECT category, SUM(amount) as spent FROM transactions WHERE type='debit' AND strftime('%Y-%m',date)=strftime('%Y-%m','now') GROUP BY category"
    ).fetchall()
    conn.close()
    spent_map = {r['category']:r['spent'] for r in spent_rows}
    result = []
    for b in budgets:
        d = dict(b)
        d['spent'] = spent_map.get(d['category'],0)
        result.append(d)
    return jsonify(result)

@app.route('/api/budgets', methods=['POST'])
def set_budget():
    data = request.json
    conn = get_db()
    conn.execute(
        'INSERT INTO budgets (category,limit_amount) VALUES (?,?) ON CONFLICT(category) DO UPDATE SET limit_amount=excluded.limit_amount',
        (data['category'], data['limit'])
    )
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/budgets/<category>', methods=['DELETE'])
def delete_budget(category):
    conn = get_db()
    conn.execute('DELETE FROM budgets WHERE category=?', (category,))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

# --- ANALYTICS (Pandas) ---
@app.route('/api/analytics/summary')
def get_summary():
    conn = get_db()
    rows = [dict(r) for r in conn.execute('SELECT * FROM transactions').fetchall()]
    conn.close()
    return jsonify(analytics.monthly_summary(rows))

@app.route('/api/analytics/categories')
def get_categories():
    conn = get_db()
    rows = [dict(r) for r in conn.execute('SELECT * FROM transactions').fetchall()]
    conn.close()
    return jsonify(analytics.category_breakdown(rows))

@app.route('/api/analytics/health_score')
def get_health_score():
    conn = get_db()
    rows = [dict(r) for r in conn.execute('SELECT * FROM transactions').fetchall()]
    budgets = [dict(b) for b in conn.execute('SELECT * FROM budgets').fetchall()]
    conn.close()
    return jsonify(analytics.health_score(rows, budgets))

# --- AI CATEGORIZE ---
@app.route('/api/ai_categorize', methods=['POST'])
def ai_categorize():
    desc = request.json.get('description','')
    return jsonify({'category': analytics.categorize(desc)})

# --- CSV ---
@app.route('/api/export/csv')
def export_csv():
    conn = get_db()
    rows = [dict(r) for r in conn.execute('SELECT * FROM transactions ORDER BY date DESC').fetchall()]
    conn.close()
    return send_file(io.BytesIO(analytics.to_csv(rows).encode()), mimetype='text/csv',
                     as_attachment=True, download_name='cashcompas.csv')

@app.route('/api/import/csv', methods=['POST'])
def import_csv():
    file = request.files.get('file')
    if not file: return jsonify({'error':'No file'}), 400
    rows, errors = analytics.parse_csv(file.stream)
    conn = get_db()
    for r in rows:
        conn.execute(
            'INSERT INTO transactions (date,description,amount,type,category,note,ai_tagged) VALUES (?,?,?,?,?,?,1)',
            (r['date'],r['description'],r['amount'],r['type'],r['category'],r.get('note',''))
        )
    conn.commit()
    conn.close()
    return jsonify({'imported':len(rows),'errors':errors})

# --- MATPLOTLIB CHARTS ---
@app.route('/api/charts/spending_pie')
def chart_spending_pie():
    conn = get_db()
    rows = [dict(r) for r in conn.execute('SELECT * FROM transactions').fetchall()]
    conn.close()
    return send_file(io.BytesIO(analytics.chart_spending_pie(rows)), mimetype='image/png')

@app.route('/api/charts/savings_trend')
def chart_savings_trend():
    conn = get_db()
    rows = [dict(r) for r in conn.execute('SELECT * FROM transactions').fetchall()]
    conn.close()
    return send_file(io.BytesIO(analytics.chart_savings_trend(rows)), mimetype='image/png')

@app.route('/api/charts/income_vs_expense')
def chart_income_vs_expense():
    conn = get_db()
    rows = [dict(r) for r in conn.execute('SELECT * FROM transactions').fetchall()]
    conn.close()
    return send_file(io.BytesIO(analytics.chart_income_vs_expense(rows)), mimetype='image/png')

if __name__ == '__main__':
    print('\n' + '='*50)
    print('  CashCompas - AI Finance Tracker')
    print('  Python + Flask + SQLite + Pandas + Matplotlib')
    print('='*50)
    print('  URL:    http://localhost:5000')
    print('  Charts: http://localhost:5000/charts')
    print('='*50 + '\n')
    app.run(host='0.0.0.0', port=5000, debug=False)
