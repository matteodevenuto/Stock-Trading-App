import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    user_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
    cash = "%.2f"%(user_cash[0]["cash"])
    stocks = db.execute("SELECT * FROM buy WHERE user_id = :user_id AND order_type = :order_type", user_id=session["user_id"], order_type='buy')
    total = 0.0
    total_profit = 0.0

    for i in range(len(stocks)):
        stock = lookup(stocks[i]["symbol"])
        stocks[i]["name"] = stock["name"]
        stocks[i]["cur_price"] = "%.2f"%(stock["price"])
        stocks[i]["cur_total"] = "%.2f"%(float(stock["price"]) * float(stocks[i]["shares"]))
        stocks[i]["profit"] = "%.2f"%(float(stocks[i]["cur_total"]) - float(stocks[i]["total"]))
        total += stocks[i]["total"]
        total_profit += float(stocks[i]["profit"])
        stocks[i]["total"] = "%.2f"%(stocks[i]["total"])

    total += float(cash)
    total = "%.2f"%(total)
    total_profit = "%.2f"%(total_profit)
    return render_template("index.html", cash=cash, stocks=stocks, total=total, total_profit=total_profit)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    symbol = request.form.get("symbol")
    shares = request.form.get("shares")
    if request.method == "GET":
        return render_template("buy.html")
    else:
        if not symbol:
            flash("No Symbol", category='error')
            return redirect("/buy")
        if not shares:
            flash("No Shares", category='error')
            return redirect("/buy")
        else:
            quote = lookup(symbol)
            if not quote:
                flash("Symbol does not exist!", category='error')
                return redirect("/buy")
            user_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
            cash = float(user_cash[0]["cash"])
            amount = quote['price'] * int(shares)
            if amount > cash:
                flash("You cannot afford this", category='error')
                return redirect("/buy")

            else:
                name = quote["name"]
                db.execute("INSERT INTO buy (user_id, symbol, shares, price, order_type, name, total) VALUES(:user_id, :symbol, :shares, :price, :order_type, :name, :total)", user_id=session["user_id"], symbol=request.form.get("symbol"), shares=request.form.get("shares"), price=quote["price"], order_type='buy', name=quote["name"], total=amount);
                db.execute("INSERT INTO history (user_id, symbol, shares, price, order_type, name, total) VALUES(:user_id, :symbol, :shares, :price, :order_type, :name, :total)", user_id=session["user_id"], symbol=request.form.get("symbol"), shares=request.form.get("shares"), price=quote["price"], order_type='buy', name=quote["name"], total=amount);
                db.execute("UPDATE users SET cash=cash-:amount WHERE id=:user_id", amount=amount, user_id=session["user_id"]);
                flash(f"You bought {shares} share(s) of {name}", category="message")
                return redirect("/")

            #TODO TODO TODO

@app.route("/history")
@login_required
def history():
    stocks = db.execute("SELECT * FROM history WHERE user_id= :user_id", user_id=session["user_id"])

    if not stocks:
        flash("You have no transaction history", category="message")
        return redirect("/history")
    else:
        return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("No Username", category='error')
            return redirect("/login")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("No Password", category='error')
            return redirect("/login")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("invalid username and/or password", category='error')
            return redirect("/login")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        return render_template("quoted.html", quote=quote, symbol=symbol)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
        if not username:
            flash("No Username", category='error')
            return redirect("/register")
        if not password:
            flash("No Password", category='error')
            return redirect("/register")
        if not confirmation:
            flash("No Password Confirmation", category='error')
            return redirect("/register")
        if confirmation != password:
            flash("Passwords must match!", category='error')
            return redirect("/register")
        else:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", (username, password_hash))
            return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    stocks = db.execute("SELECT * FROM buy WHERE user_id = :user_id AND order_type = :order_type", user_id=session["user_id"], order_type='buy')

    for i in range(len(stocks)):
        stock = lookup(stocks[i]["symbol"])
        stocks[i]["name"] = stock["name"]
        stocks[i]["cur_price"] = "%.2f"%(stock["price"])
        stocks[i]["cur_total"] = "%.2f"%(float(stock["price"]) * float(stocks[i]["shares"]))
        stocks[i]["profit"] = "%.2f"%(float(stocks[i]["cur_total"]) - float(stocks[i]["total"]))

    if request.method == "GET":
        return render_template("sell.html", stocks=stocks)
    else:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            flash("Missing symbol", category="error")
            return redirect("/sell")
        if not shares or int(shares) < 1:
            flash("Missing shares", category="error")
            return redirect("/sell")
        else:
            stocks = db.execute("SELECT * FROM buy WHERE user_id = :user_id", user_id=session["user_id"])
            stock_sell = db.execute("SELECT * FROM buy WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=symbol)
            owned_shares = int(stock_sell[0]["shares"])
            owned_price = int(stock_sell[0]["price"])
            if int(shares) > owned_shares:
                flash("You do not own that many shares", category="error")
                return redirect("/sell")
            else:
                quote = lookup(symbol)
                amount = quote["price"] * int(shares)
                name = quote["name"]
                if int(shares) == owned_shares:
                    db.execute("DELETE FROM buy WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=symbol)
                if int(shares) < owned_shares:
                    new_shares = owned_shares - int(shares)
                    new_total = float(new_shares) * owned_price
                    db.execute("UPDATE buy SET shares = :shares, total = :total WHERE user_id = :user_id AND symbol = :symbol", shares=new_shares, total=new_total, user_id=session["user_id"], symbol=symbol)
                db.execute("INSERT INTO sell (user_id, symbol, shares, price, order_type, name, total) VALUES(:user_id, :symbol, :shares, :price, :order_type, :name, :total)", user_id=session["user_id"], symbol=request.form.get("symbol"), shares=request.form.get("shares"), price=quote["price"], order_type='sell', name=quote["name"], total=amount);
                db.execute("INSERT INTO history (user_id, symbol, shares, price, order_type, name, total) VALUES(:user_id, :symbol, -:shares, :price, :order_type, :name, :total)", user_id=session["user_id"], symbol=request.form.get("symbol"), shares=request.form.get("shares"), price=quote["price"], order_type='sell', name=quote["name"], total=amount);
                db.execute("UPDATE users SET cash=cash+:amount WHERE id=:user_id", amount=amount, user_id=session["user_id"]);
                flash(f"You sold {shares} share(s) of {name}", category="message")
                return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
