
import os
import sqlite3
from uuid import uuid4
from flask import Flask, request, redirect, url_for, session, render_template_string, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")

UPLOAD_FOLDER = "uploads"
ALLOWED = {"pdf", "jpg", "jpeg", "png", "xls", "xlsx"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def db():
    con = sqlite3.connect("orders.db")
    con.row_factory = sqlite3.Row
    return con

with db() as con:
    con.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        pages INTEGER,
        print_type TEXT,
        amount INTEGER,
        status TEXT DEFAULT 'Pending',
        payment TEXT DEFAULT '',
        paid INTEGER DEFAULT 0
    )
    """)

def page(content):
    return render_template_string("""
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Naya Navela Print Portal</title>
    <style>
    body{font-family:Arial;background:#f2f4f8;margin:0;padding:20px}
    .box{max-width:650px;margin:25px auto;background:white;padding:25px;
    border-radius:14px;box-shadow:0 2px 12px #ddd}
    h1{color:#421052} input,select,button{width:100%;padding:12px;
    margin:9px 0;box-sizing:border-box;border:1px solid #ccc;border-radius:7px}
    button{background:#421052;color:white;font-weight:bold;cursor:pointer}
    .order{padding:15px;background:#f5f5f5;margin:12px 0;border-radius:8px}
    a{color:#421052}
    </style></head><body><div class="box">
    <h1>NAYA NAVELA</h1><p>Print & Xerox Service</p>
    """ + content + "</div></body></html>")

@app.route("/")
def home():
    return page("""
    <h2>Upload Your Document</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
    <label>Select File (PDF, JPG, PNG, XLS, XLSX)</label>
    <input type="file" name="file" required>
    <label>Number of Pages</label>
    <input type="number" name="pages" min="1" max="500" required>
    <label>Print Type</label>
    <select name="print_type">
    <option value="BW">Black & White - ₹5/page</option>
    <option value="Color">Color - ₹10/page</option>
    </select>
    <button>Submit Print Request</button></form>
    <p><a href="/admin">Admin Login</a></p>
    """)

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return "Please select a file"
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return "File type not allowed"

    try:
        pages = int(request.form["pages"])
        if not 1 <= pages <= 500:
            return "Invalid page count"
    except ValueError:
        return "Invalid page count"

    print_type = request.form["print_type"]
    if print_type not in ("BW", "Color"):
        return "Invalid print type"

    amount = pages * (5 if print_type == "BW" else 10)
    filename = str(uuid4()) + "_" + secure_filename(f.filename)
    f.save(os.path.join(UPLOAD_FOLDER, filename))

    with db() as con:
        cur = con.execute(
            "INSERT INTO orders(filename,pages,print_type,amount) VALUES(?,?,?,?)",
            (filename, pages, print_type, amount)
        )
        order_id = cur.lastrowid

    return page(f"""
    <h2>Request Submitted!</h2>
    <p>Your Order Number: <b>#{order_id}</b></p>
    <p>Total Amount: <b>₹{amount}</b></p>
    <p>Please wait. Shop owner will accept your order first.</p>
    <a href="/status/{order_id}">Check Order Status</a>
    """)

@app.route("/status/<int:oid>")
def status(oid):
    with db() as con:
        order = con.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not order:
        return "Order not found"

    if order["status"] == "Rejected":
        return page("<h2>Sorry, your order was rejected.</h2>")
    if order["status"] == "Pending":
        return page("<h2>Order Pending</h2><p>Please wait for shop approval.</p>")

    if order["status"] == "Accepted":
        return page(f"""
        <h2>Order Accepted!</h2>
        <p>Amount: ₹{order['amount']}</p>
        <form method="post" action="/payment/{oid}">
        <select name="payment">
        <option value="UPI">Online UPI</option>
        <option value="Cash">Cash at Shop</option>
        </select><button>Continue</button></form>
        """)

    if order["paid"]:
        return page("<h2>Payment Confirmed!</h2><p>Your order is being processed.</p>")

    return page(f"<h2>Payment Selected: {order['payment']}</h2><p>Waiting for shop payment confirmation.</p>")

@app.route("/payment/<int:oid>", methods=["POST"])
def payment(oid):
    method = request.form.get("payment")
    if method not in ("UPI", "Cash"):
        return "Invalid payment method"
    with db() as con:
        con.execute("UPDATE orders SET payment=?, status='Payment Pending' WHERE id=? AND status='Accepted'", (method, oid))
    if method == "UPI":
        return page("""
        <h2>Pay using Navi UPI</h2>
<h2>Pay using Navi UPI</h2>

<img src="/static/navi-qr.jpeg"
     alt="Navi UPI QR Code"
     style="width:100%;max-width:350px;display:block;margin:auto;">

<h3>UPI ID</h3>
<p>niteshhd60149@naviaxis</p>

<p>Payment करने के बाद दुकान मालिक को सूचित करें।</p>        <p>After payment, shop owner will verify it.</p>
        """)
    return page("<h2>Cash Selected</h2><p>Please pay at the shop counter.</p>")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
        else:
            return page("<h3>Wrong Password</h3><a href='/admin'>Try again</a>")

    if not session.get("admin"):
        return page("""
        <h2>Admin Login</h2>
        <form method="post"><input type="password" name="password"
        placeholder="Admin Password" required><button>Login</button></form>
        """)

    with db() as con:
        orders = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()

    content = "<h2>Admin Dashboard</h2>"
    for o in orders:
        content += f"""
        <div class="order">
        <b>Order #{o['id']}</b><br>
        File: {o['filename'].split('_',1)[-1]}<br>
        Pages: {o['pages']} | Type: {o['print_type']}<br>
        Amount: ₹{o['amount']}<br>
        Status: {o['status']} | Payment: {o['payment']}<br>
        <a href="/download/{o['id']}">Download File</a>
        <form method="post" action="/action/{o['id']}">
        <button name="action" value="Accept">Accept Order</button>
        <button name="action" value="Reject">Reject Order</button>
        <button name="action" value="Paid">Confirm Payment</button>
        </form></div>
        """
    content += "<a href='/logout'>Logout</a>"
    return page(content)

@app.route("/action/<int:oid>", methods=["POST"])
def action(oid):
    if not session.get("admin"):
        return redirect("/admin")
    act = request.form.get("action")
    if act == "Accept":
        status = "Accepted"
    elif act == "Reject":
        status = "Rejected"
    elif act == "Paid":
        with db() as con:
            con.execute("UPDATE orders SET paid=1 WHERE id=?", (oid,))
        return redirect("/admin")
    else:
        return "Invalid action"
    with db() as con:
        con.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    return redirect("/admin")

@app.route("/download/<int:oid>")
def download(oid):
    if not session.get("admin"):
        return redirect("/admin")
    from flask import send_from_directory
    with db() as con:
        order = con.execute("SELECT filename FROM orders WHERE id=?", (oid,)).fetchone()
    if not order:
        return "Order not found"
    return send_from_directory(UPLOAD_FOLDER, order["filename"], as_attachment=True)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
