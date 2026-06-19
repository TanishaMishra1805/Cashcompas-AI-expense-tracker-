"""
analytics.py — Pandas + Matplotlib powered analytics for CashCompas
"""

import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime

# ─── AI KEYWORD CATEGORIZER ──────────────────────────────────────────────────

AI_KEYWORDS = {
    'swiggy': 'Food & Dining', 'zomato': 'Food & Dining', 'food': 'Food & Dining',
    'restaurant': 'Food & Dining', 'cafe': 'Food & Dining', 'coffee': 'Food & Dining',
    'lunch': 'Food & Dining', 'dinner': 'Food & Dining', 'breakfast': 'Food & Dining',
    'pizza': 'Food & Dining', 'burger': 'Food & Dining', 'dhaba': 'Food & Dining',
    'uber': 'Travel', 'ola': 'Travel', 'petrol': 'Travel', 'diesel': 'Travel',
    'flight': 'Travel', 'train': 'Travel', 'bus': 'Travel', 'metro': 'Travel',
    'hotel': 'Travel', 'trip': 'Travel', 'irctc': 'Travel', 'rapido': 'Travel',
    'electricity': 'Bills & Utilities', 'water': 'Bills & Utilities',
    'internet': 'Bills & Utilities', 'wifi': 'Bills & Utilities',
    'recharge': 'Bills & Utilities', 'rent': 'Bills & Utilities',
    'gas': 'Bills & Utilities', 'broadband': 'Bills & Utilities', 'jio': 'Bills & Utilities',
    'amazon': 'Shopping', 'flipkart': 'Shopping', 'myntra': 'Shopping',
    'meesho': 'Shopping', 'clothes': 'Shopping', 'shopping': 'Shopping',
    'shoes': 'Shopping', 'fashion': 'Shopping', 'ajio': 'Shopping', 'nykaa': 'Shopping',
    'netflix': 'Entertainment', 'hotstar': 'Entertainment', 'prime': 'Entertainment',
    'movie': 'Entertainment', 'concert': 'Entertainment', 'game': 'Entertainment',
    'spotify': 'Entertainment', 'youtube': 'Entertainment', 'pvr': 'Entertainment',
    'hospital': 'Healthcare', 'medicine': 'Healthcare', 'pharmacy': 'Healthcare',
    'doctor': 'Healthcare', 'dental': 'Healthcare', 'gym': 'Healthcare',
    'medical': 'Healthcare', 'chemist': 'Healthcare', 'apollo': 'Healthcare',
    'course': 'Education', 'book': 'Education', 'class': 'Education',
    'fees': 'Education', 'tuition': 'Education', 'coaching': 'Education',
    'udemy': 'Education', 'college': 'Education',
    'mutual fund': 'Investments', 'sip': 'Investments', 'stock': 'Investments',
    'gold': 'Investments', 'zerodha': 'Investments', 'groww': 'Investments',
    'etf': 'Investments', 'nifty': 'Investments',
}

def categorize(description: str) -> str:
    d = description.lower()
    for kw, cat in AI_KEYWORDS.items():
        if kw in d:
            return cat
    return 'Others'


# ─── DATAFRAME HELPER ─────────────────────────────────────────────────────────

def to_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=['id','date','description','amount','type','category','note','ai_tagged'])
    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    df['month'] = df['date'].dt.to_period('M')
    return df


# ─── MONTHLY SUMMARY ──────────────────────────────────────────────────────────

def monthly_summary(rows: list[dict]) -> list[dict]:
    df = to_df(rows)
    if df.empty:
        return []

    income  = df[df['type'] == 'credit'].groupby('month')['amount'].sum()
    expense = df[df['type'] == 'debit'].groupby('month')['amount'].sum()

    months = sorted(set(income.index) | set(expense.index))
    result = []
    for m in months[-6:]:  # last 6 months
        inc = float(income.get(m, 0))
        exp = float(expense.get(m, 0))
        sav = inc - exp
        result.append({
            'month':   str(m),
            'income':  inc,
            'expense': exp,
            'savings': sav,
            'rate':    round(sav / inc * 100, 1) if inc > 0 else 0,
        })
    return result


# ─── CATEGORY BREAKDOWN ───────────────────────────────────────────────────────

def category_breakdown(rows: list[dict]) -> list[dict]:
    df = to_df(rows)
    if df.empty:
        return []

    # This month only
    now = pd.Timestamp.now().to_period('M')
    this_month = df[(df['type'] == 'debit') & (df['month'] == now)]
    breakdown  = this_month.groupby('category')['amount'].sum().sort_values(ascending=False)
    total      = breakdown.sum()

    return [
        {
            'category': cat,
            'amount':   float(amt),
            'pct':      round(float(amt) / total * 100, 1) if total > 0 else 0,
        }
        for cat, amt in breakdown.items()
    ]


# ─── SAVINGS TREND ────────────────────────────────────────────────────────────

def savings_trend(rows: list[dict]) -> list[dict]:
    summary = monthly_summary(rows)
    running = 0
    result  = []
    for s in summary:
        running += s['savings']
        result.append({'month': s['month'], 'savings': s['savings'], 'cumulative': running})
    return result


# ─── FINANCIAL HEALTH SCORE ───────────────────────────────────────────────────

def health_score(rows: list[dict], budgets: list[dict]) -> dict:
    df = to_df(rows)
    if df.empty:
        return {'score': 0, 'factors': []}

    now     = pd.Timestamp.now().to_period('M')
    monthly = df[df['month'] == now]
    income  = float(monthly[monthly['type'] == 'credit']['amount'].sum())
    expense = float(monthly[monthly['type'] == 'debit']['amount'].sum())
    savings = income - expense
    rate    = (savings / income * 100) if income > 0 else 0

    # Factor 1: Savings rate (max 30)
    sav_score = min(30, int(rate * 1.5))

    # Factor 2: Budget adherence (max 25)
    bud_score = 25
    if budgets:
        spent_map = {}
        for r in monthly[monthly['type'] == 'debit'].groupby('category')['amount'].sum().items():
            spent_map[r[0]] = float(r[1])
        over_count = sum(1 for b in budgets if spent_map.get(b['category'], 0) > b['limit_amount'])
        bud_score = max(0, 25 - over_count * 8)

    # Factor 3: Investment habit (max 20)
    inv = float(monthly[monthly['category'] == 'Investments']['amount'].sum())
    inv_score = min(20, int(inv / income * 100)) if income > 0 else 0

    # Factor 4: Expense diversity (max 15) — not over-spending on single category
    if expense > 0:
        top_cat_pct = float(monthly[monthly['type'] == 'debit'].groupby('category')['amount'].sum().max()) / expense * 100
        div_score   = max(0, 15 - int((top_cat_pct - 40) / 5)) if top_cat_pct > 40 else 15
    else:
        div_score = 15

    # Factor 5: Consistency (max 10)
    months_active = df['month'].nunique()
    con_score     = min(10, months_active * 3)

    total = sav_score + bud_score + inv_score + div_score + con_score

    return {
        'score': total,
        'factors': [
            {'name': 'Savings Rate',       'score': sav_score, 'max': 30},
            {'name': 'Budget Adherence',   'score': bud_score, 'max': 25},
            {'name': 'Investment Habit',   'score': inv_score, 'max': 20},
            {'name': 'Expense Diversity',  'score': div_score, 'max': 15},
            {'name': 'Consistency',        'score': con_score, 'max': 10},
        ]
    }


# ─── CSV EXPORT ───────────────────────────────────────────────────────────────

def to_csv(rows: list[dict]) -> str:
    if not rows:
        return 'date,description,amount,type,category,note\n'
    df = pd.DataFrame(rows)[['date', 'description', 'amount', 'type', 'category', 'note']]
    return df.to_csv(index=False)


# ─── CSV IMPORT ───────────────────────────────────────────────────────────────

def parse_csv(stream) -> tuple[list[dict], list[str]]:
    try:
        df = pd.read_csv(stream)
    except Exception as e:
        return [], [str(e)]

    df.columns = [c.strip().lower() for c in df.columns]
    rows, errors = [], []

    for i, row in df.iterrows():
        try:
            amt  = abs(float(row.get('amount', 0)))
            desc = str(row.get('description', row.get('desc', 'Imported'))).strip()
            date = str(row.get('date', datetime.now().strftime('%Y-%m-%d'))).strip()[:10]
            cat  = str(row.get('category', '')).strip() or categorize(desc)
            typ  = str(row.get('type', 'debit')).strip().lower()
            if typ not in ('debit', 'credit'):
                typ = 'debit' if amt >= 0 else 'credit'
            note = str(row.get('note', '')).strip()
            if not desc or amt <= 0:
                continue
            rows.append({'date': date, 'description': desc, 'amount': amt,
                         'type': typ, 'category': cat, 'note': note})
        except Exception as e:
            errors.append(f'Row {i}: {e}')

    return rows, errors


# ─── MATPLOTLIB CHART GENERATORS ─────────────────────────────────────────────
# These produce real server-side PNG images using Matplotlib + Pandas
# Called by Flask routes → returned as image/png bytes

DARK_BG   = '#0f0f13'
CARD_BG   = '#1a1a25'
TEXT_COL  = '#9090b0'
GRID_COL  = '#2a2a3d'

CAT_COLORS = {
    'Food & Dining':'#4f8ef7','Travel':'#a855f7','Bills & Utilities':'#14b8a6',
    'Shopping':'#f59e0b','Entertainment':'#ec4899','Healthcare':'#22c55e',
    'Education':'#06b6d4','Investments':'#8b5cf6','Others':'#6b7280',
}

def _style_ax(fig, ax):
    """Apply dark theme to a matplotlib figure."""
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(CARD_BG)
    ax.tick_params(colors=TEXT_COL, labelsize=9)
    ax.xaxis.label.set_color(TEXT_COL)
    ax.yaxis.label.set_color(TEXT_COL)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COL)
    ax.grid(color=GRID_COL, linewidth=0.5, alpha=0.7)


def chart_spending_pie(rows: list[dict]) -> bytes:
    """Donut chart of this month's spending by category."""
    df  = to_df(rows)
    now = pd.Timestamp.now().to_period('M')
    df  = df[(df['type'] == 'debit') & (df['month'] == now)]
    if df.empty:
        df = to_df(rows)[to_df(rows)['type'] == 'debit']  # fallback: all data

    breakdown = df.groupby('category')['amount'].sum().sort_values(ascending=False)
    colors    = [CAT_COLORS.get(c, '#6b7280') for c in breakdown.index]

    fig, ax = plt.subplots(figsize=(6, 5), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)
    wedges, texts, autotexts = ax.pie(
        breakdown.values, labels=breakdown.index, autopct='%1.1f%%',
        colors=colors, startangle=90, pctdistance=0.75,
        wedgeprops=dict(width=0.55, edgecolor=DARK_BG, linewidth=2),
    )
    for t in texts:       t.set_color(TEXT_COL); t.set_fontsize(9)
    for t in autotexts:   t.set_color('#ffffff'); t.set_fontsize(8); t.set_fontweight('bold')
    ax.set_title('Spending by Category', color='#e8e8f0', fontsize=13, fontweight='bold', pad=16)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight', facecolor=DARK_BG)
    plt.close(fig)
    return buf.getvalue()


def chart_savings_trend(rows: list[dict]) -> bytes:
    """Line chart of monthly savings trend."""
    summary = monthly_summary(rows)
    if not summary:
        summary = [{'month':'2026-06','savings':0,'income':0,'expense':0,'rate':0}]

    months  = [s['month']   for s in summary]
    savings = [s['savings'] for s in summary]

    fig, ax = plt.subplots(figsize=(7, 4), facecolor=DARK_BG)
    _style_ax(fig, ax)

    ax.plot(months, savings, color='#4f8ef7', linewidth=2.5, marker='o',
            markersize=7, markerfacecolor='#4f8ef7', markeredgecolor=DARK_BG, markeredgewidth=2)
    ax.fill_between(months, savings, alpha=0.15, color='#4f8ef7')

    ax.set_title('Monthly Savings Trend', color='#e8e8f0', fontsize=13, fontweight='bold', pad=14)
    ax.set_ylabel('Amount (₹)', color=TEXT_COL, fontsize=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'₹{int(v/1000)}k'))
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(months, rotation=30, ha='right')

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight', facecolor=DARK_BG)
    plt.close(fig)
    return buf.getvalue()


def chart_income_vs_expense(rows: list[dict]) -> bytes:
    """Grouped bar chart: income vs expenses per month."""
    summary = monthly_summary(rows)
    if not summary:
        summary = [{'month':'2026-06','income':0,'expense':0,'savings':0,'rate':0}]

    months  = [s['month']   for s in summary]
    incomes = [s['income']  for s in summary]
    expense = [s['expense'] for s in summary]

    x   = range(len(months))
    w   = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor=DARK_BG)
    _style_ax(fig, ax)

    bars1 = ax.bar([i - w/2 for i in x], incomes, w, label='Income',  color='#22c55e', alpha=0.85)
    bars2 = ax.bar([i + w/2 for i in x], expense, w, label='Expense', color='#ef4444', alpha=0.85)

    # Value labels on bars
    for bar in list(bars1) + list(bars2):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 500, f'₹{int(h/1000)}k',
                ha='center', va='bottom', color=TEXT_COL, fontsize=8)

    ax.set_xticks(list(x), labels=months, rotation=30, ha='right')
    ax.set_ylabel('Amount (₹)', color=TEXT_COL, fontsize=10)
    ax.set_title('Income vs Expenses (Monthly)', color='#e8e8f0', fontsize=13, fontweight='bold', pad=14)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'₹{int(v/1000)}k'))
    ax.legend(facecolor=CARD_BG, edgecolor=GRID_COL, labelcolor=TEXT_COL, fontsize=10)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight', facecolor=DARK_BG)
    plt.close(fig)
    return buf.getvalue()
