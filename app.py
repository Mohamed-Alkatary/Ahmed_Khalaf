from flask import Flask, render_template, request, redirect, session, send_file
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import date

app = Flask(__name__)
app.secret_key = "secret123"

# ======================
# Google Sheets
# ======================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

url = "https://docs.google.com/spreadsheets/d/1vClyD6Pn5OaciAtC74pNvmxuDrr4Qn2p8BDOyqlik2Y/edit"

users_sheet = client.open_by_url(url).worksheet("users")
customers_sheet = client.open_by_url(url).worksheet("customers")
suppliers_sheet = client.open_by_url(url).worksheet("suppliers")
transactions_sheet = client.open_by_url(url).worksheet("transactions")
payments_sheet = client.open_by_url(url).worksheet("payments")

# ======================
# Login (🔥 تم إضافة role)
# ======================
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','').strip()

        for row in users_sheet.get_all_records():
            if str(row['username']).strip() == u and str(row['password']).strip() == p:
                session['user'] = u
                session['role'] = row.get('role','user')  # 🔥 مهم
                return redirect('/dashboard')

        return render_template('login.html', error="❌ بيانات غلط")

    return render_template('login.html')

# ======================
# Dashboard
# ======================
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    customers = customers_sheet.get_all_records()
    suppliers = suppliers_sheet.get_all_records()
    transactions = transactions_sheet.get_all_records()
    payments = payments_sheet.get_all_records()

    # 🔥 القديم
    customer_total = 0
    supplier_total = 0

    for t in transactions:
        try:
            total = float(t.get('total', 0))
        except:
            total = 0

        t_type = str(t.get('type','')).strip().lower()

        if 'customer' in t_type or 'عميل' in t_type:
            customer_total += total
        elif 'supplier' in t_type or 'مورد' in t_type:
            supplier_total += total

    # 🔥 الجديد (الكاش)
    total_in = 0
    total_out = 0
    methods = {}

    for p in payments:
        amount = float(p.get('amount', 0))
        method = p.get('method', 'غير محدد')

        if p.get('type') == 'customer':
            total_in += amount
        else:
            total_out += amount

        methods[method] = methods.get(method, 0) + amount

    net = total_in - total_out

    return render_template(
        'dashboard.html',
        user=session['user'],

        # القديم
        total_customers=len(customers),
        total_suppliers=len(suppliers),
        customer_total=customer_total,
        supplier_total=supplier_total,

        # الجديد
        total_in=total_in,
        total_out=total_out,
        net=net,
        methods=methods
    )
# ======================
# Transactions
# ======================
@app.route('/transactions', methods=['GET','POST'])
def transactions():
    customers = customers_sheet.get_all_records()
    suppliers = suppliers_sheet.get_all_records()

    if request.method == 'POST':

        q = float(request.form.get('quantity', 0) or 0)
        p = float(request.form.get('price', 0) or 0)
        total = q * p

        # 🔥 المقاسات
        sizes = request.form.getlist('size')
        sizes_str = ",".join(sizes)

        transactions_sheet.append_row([
            request.form.get('type'),
            request.form.get('name'),
            request.form.get('product'),
            sizes_str,
            request.form.get('quantity'),
            request.form.get('price'),
            total,
            request.form.get('date')
        ])

        return redirect('/transactions')

    data = transactions_sheet.get_all_records()

    # إضافة index
    for i, row in enumerate(data):
        row['index'] = i

    return render_template(
        'transactions.html',
        customers=customers,
        suppliers=suppliers,
        data=data,
        current_date=date.today().strftime('%Y-%m-%d')
    )
##===========
# ======================
# Customers
# ======================
@app.route('/customers', methods=['GET','POST'])
def customers():
    if 'user' not in session:
        return redirect('/')

    if request.method == 'POST':
        customers_sheet.append_row([
            request.form.get('name'),
            request.form.get('phone'),
            request.form.get('total')
        ])
        return redirect('/customers')

    return render_template(
        'customers.html',
        data=customers_sheet.get_all_records(),
        role=session.get('role')
    )

# ======================
# Suppliers
# ======================
@app.route('/suppliers', methods=['GET','POST'])
def suppliers():
    if 'user' not in session:
        return redirect('/')

    if request.method == 'POST':
        suppliers_sheet.append_row([
            request.form.get('name'),
            request.form.get('phone'),
            request.form.get('total')
        ])
        return redirect('/suppliers')

    return render_template(
        'suppliers.html',
        data=suppliers_sheet.get_all_records(),
        role=session.get('role')
    )
# Payments
# ======================
@app.route('/payments', methods=['GET','POST'])
def payments():
    customers = customers_sheet.get_all_records()
    suppliers = suppliers_sheet.get_all_records()

    if request.method == 'POST':
        payments_sheet.append_row([
            request.form.get('type'),
            request.form.get('name'),
            request.form.get('method'),
            request.form.get('amount'),
            request.form.get('date')
        ])
        return redirect('/payments')

    return render_template(
        'payments.html',
        customers=customers,
        suppliers=suppliers
    )

# ======================
# Reports
# ======================
@app.route('/reports', methods=['GET','POST'])
def reports():
    customers = customers_sheet.get_all_records()
    suppliers = suppliers_sheet.get_all_records()

    data = []
    summary = {}

    if request.method == 'POST':
        acc_type = request.form.get('type')
        name = request.form.get('name')

        t_data = transactions_sheet.get_all_records()
        p_data = payments_sheet.get_all_records()

        opening = 0

        if acc_type == 'customer':
            for c in customers:
                if c['name'] == name:
                    opening = float(c.get('total',0))
        else:
            for s in suppliers:
                if s['name'] == name:
                    opening = float(s.get('total',0))

        balance = opening

        for t in t_data:
            if t['name'] == name:
                total = float(t.get('total',0))

                if acc_type == 'customer':
                    balance += total
                else:
                    balance -= total

                data.append({
                    "date": t['date'],
                    "type": "عملية",
                    "name": name,
                    "desc": f"{t['product']} - {t.get('size','')}",
                    "debit": total,
                    "credit": 0,
                    "balance": balance
                })

        for p in p_data:
            if p['name'] == name:
                amount = float(p.get('amount',0))

                if acc_type == 'customer':
                    balance -= amount
                else:
                    balance += amount

                data.append({
                    "date": p['date'],
                    "type": "سداد",
                    "name": name,
                    "desc": p['method'],
                    "debit": 0,
                    "credit": amount,
                    "balance": balance
                })

        data = sorted(data, key=lambda x: x['date'])

        summary = {
            "name": name,
            "opening": opening,
            "balance": balance
        }

        session['report_data'] = data

    return render_template(
        'reports.html',
        customers=customers,
        suppliers=suppliers,
        data=data,
        summary=summary
    )

# ======================
@app.route('/daily_closing', methods=['GET','POST'])
def daily_closing():
    payments = payments_sheet.get_all_records()

    methods = [
        "فودافون 1","فودافون 2","فودافون 3",
        "فودافون 4","فودافون 5",
        "بنك","انستاباي","كاش"
    ]

    report = []
    details = []

    from_date = None
    to_date = None
    selected_method = None

    if request.method == 'POST':
        from_date = request.form.get('from_date')
        to_date = request.form.get('to_date')
        selected_method = request.form.get('method')

    for m in methods:

        # فلتر وسيلة الدفع
        if selected_method and m != selected_method:
            continue

        incoming = 0
        outgoing = 0

        for p in payments:
            date_val = p.get('date')

            if from_date and date_val < from_date:
                continue
            if to_date and date_val > to_date:
                continue

            if p['method'] == m:

                amount = float(p.get('amount',0))

                if p['type'] == 'customer':
                    incoming += amount

                    details.append({
                        "date": date_val,
                        "method": m,
                        "type": "تحصيل",
                        "name": p['name'],
                        "amount": amount
                    })

                else:
                    outgoing += amount

                    details.append({
                        "date": date_val,
                        "method": m,
                        "type": "سداد",
                        "name": p['name'],
                        "amount": amount
                    })

        report.append({
            "method": m,
            "in": incoming,
            "out": outgoing,
            "balance": incoming - outgoing
        })

    session['closing_data'] = details

    return render_template(
        'daily_closing.html',
        report=report,
        details=details,
        methods=methods,
        from_date=from_date,
        to_date=to_date,
        selected_method=selected_method
    )

    # حفظ للإكسل
    session['closing_data'] = details

    return render_template(
        'daily_closing.html',
        report=report,
        details=details,
        from_date=from_date,
        to_date=to_date
    )
# Excel
@app.route('/export_closing_excel')
def export_closing_excel():
    data = session.get('closing_data', [])

    df = pd.DataFrame(data)

    file_path = "closing.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)
# ======================
@app.route('/export_excel', methods=['POST'])
def export_excel():
    data = session.get('report_data', [])

    df = pd.DataFrame(data)
    df = df[["date","type","name","desc","debit","credit","balance"]]

    file_path = "report.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)

# ======================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ======================
if __name__ == '__main__':
    app.run(debug=True)
#######Late customers/suppliers report
from datetime import datetime

@app.route('/late_customers')
def late_customers():

    customers = customers_sheet.get_all_records()
    transactions = transactions_sheet.get_all_records()
    payments = payments_sheet.get_all_records()

    result = []

    today = datetime.today()

    for c in customers:
        name = c['name']

        last_payment = None
        last_transaction = None

        # آخر سداد
        for p in payments:
            if p['name'] == name and p['type'] == 'customer':
                d = datetime.strptime(p['date'], "%Y-%m-%d")

                if not last_payment or d > last_payment:
                    last_payment = d

        # آخر سحب
        for t in transactions:
            if t['name'] == name and t['type'] == 'customer':
                d = datetime.strptime(t['date'], "%Y-%m-%d")

                if not last_transaction or d > last_transaction:
                    last_transaction = d

        # فرق الأيام
        days = None
        if last_payment:
            days = (today - last_payment).days

        result.append({
            "name": name,
            "last_payment": last_payment,
            "last_transaction": last_transaction,
            "days": days
        })
