import os

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from flask_sqlalchemy import SQLAlchemy

from sqlalchemy import text

from helpers import apology, login_required, lookup, usd, percent, search, check_env_vars, format_date
from datetime import datetime
import requests

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["percent"] = percent
app.jinja_env.filters["format_date"] = format_date

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure the SQLAlchemy database URI to use a SQLite database located in the main folder and named 'finance.db'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(
    basedir, 'finance.db')

# Set the SQLALCHEMY_ECHO configuration key to True to enable logging of SQL statements
app.config['SQLALCHEMY_ECHO'] = True

# Create a SQLAlchemy instance
db = SQLAlchemy(app)

# Create database if not exists
sql_init_commands = [
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, username TEXT NOT NULL, hash TEXT NOT NULL, cash NUMERIC NOT NULL DEFAULT 10000.00);",
    "CREATE UNIQUE INDEX IF NOT EXISTS username ON users (username);",
    "CREATE TABLE IF NOT EXISTS transactions(user_id INTEGER, orderid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, name TEXT NOT NULL, symbol TEXT NOT NULL, type TEXT NOT NULL, price NUMERIC NOT NULL, shares INTEGER NOT NULL, date TEXT NOT NULL, FOREIGN KEY (user_id) REFERENCES users(id));",
    "CREATE TABLE IF NOT EXISTS wallet(user_id INTEGER, name TEXT NOT NULL, symbol TEXT NOT NULL, shares INTEGER NOT NULL, FOREIGN KEY (user_id) REFERENCES users(id));"
]

if not os.path.exists(os.path.join(basedir, 'finance.db')):
    with app.app_context():
        with db.engine.connect() as connection:
            for command in sql_init_commands:
                connection.execute(text(command))
else:
    print("Database already exists.")

# Make sure environmental variables are set
required_env_vars = ["API_KEY", "HCAPTCHA_SITE_KEY", "HCAPTCHA_SECRET_KEY"]
check_env_vars(required_env_vars)

# Retrieve environment variables
HCAPTCHA_SITE_KEY = os.environ.get("HCAPTCHA_SITE_KEY")
HCAPTCHA_SECRET_KEY = os.environ.get("HCAPTCHA_SECRET_KEY")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    wallet = db.session.execute(
        text("SELECT name, symbol, shares FROM wallet WHERE user_id = :user_id"
             ), {"user_id": session["user_id"]})
    cash = db.session.execute(text("SELECT cash FROM users WHERE id = :id"),
                              {"id": session["user_id"]})
    buy_transactions = db.session.execute(
        text(
            "SELECT symbol, SUM(price * shares) AS purchased, SUM(shares) AS buyed_shares FROM transactions WHERE user_id = :user_id AND type = 'buy' GROUP BY symbol"
        ), {"user_id": session["user_id"]})

    # Get all row data from query and represent as dictionary
    wallet = wallet.mappings().all()
    cash = cash.mappings().all()
    buy_transactions = buy_transactions.mappings().all()

    total_stock_value = 0
    index = []

    # Iterate through each row of wallet
    for row in wallet:

        # Get data from current wallet table row
        name = row["name"]
        symbol = row["symbol"]
        shares = row["shares"]

        # Check current price using api request
        quote = lookup(symbol)

        # Current share price and value of all shares
        current_price = quote["price"]
        value = shares * current_price

        # Get total cost of purchases and number of buyd shares for given symbol
        purchased = next(item for item in buy_transactions
                         if item["symbol"] == symbol)["purchased"]
        buyed_shares = next(item for item in buy_transactions
                            if item["symbol"] == symbol)["buyed_shares"]

        average_cost_per_share = purchased / buyed_shares

        total_investment = average_cost_per_share * shares

        net_profit = value - total_investment

        percent_profit = net_profit / total_investment * 100

        # Populate index dictionary with information to display
        entry = {
            "name": name,
            "symbol": symbol,
            "shares": shares,
            "price": current_price,
            "value": value,
            "invested": total_investment,
            "net_profit": net_profit,
            "percent_profit": percent_profit
        }

        index.append(entry)

        # Sum of all stock values
        total_stock_value += value

    # Sum of stock value and cash
    total = total_stock_value + cash[0]["cash"]

    return render_template("index.html",
                           index=index,
                           total_stock_value=total_stock_value,
                           cash=cash[0]["cash"],
                           total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        # Ensure symbol was submitted
        if not symbol:
            return apology("You must provide a symbol.", 400)

        # Check if proper symbol was submitted
        if not lookup(symbol):
            return apology(
                "Invalid stock symbol. Use the search function to look for suitable symbols.",
                400)

        # Ensure share was submitted
        if not shares:
            return apology("You must provide shares.", 400)

        # Check if number was submited
        try:
            int(shares)
        except:
            return apology("The number of shares must be an integer.", 400)

        # Check if positiv integer was submited
        if int(shares) <= 0:
            return apology("The number of shares must be a positive integer.",
                           400)

        # all checks for input passed

        # Look up the stock using the symbol provided by the user
        stock = lookup(request.form.get("symbol"))

        # Retrieve the current user's cash balance from the database, convert the result to a list of dictionaries
        cash = db.session.execute(
            text("SELECT cash FROM users WHERE id = :id"),
            {"id": session["user_id"]})
        cash = cash.mappings().all()

        # Calculate the total price of the transaction
        total_price = stock["price"] * int(shares)

        # Check if user have enough cash
        if cash[0]["cash"] < total_price:
            return apology("You need to provide more cash.", 403)

        # Updating database
        # Add transaction
        db.session.execute(
            text(
                "INSERT INTO transactions (user_id, name, symbol, type, price, shares, date) VALUES (:user_id, :name, :symbol, :type, :price, :shares, :date)"
            ), {
                "user_id": session["user_id"],
                "name": stock["name"],
                "symbol": stock["symbol"],
                "type": 'buy',
                "price": stock["price"],
                "shares": int(shares),
                "date": datetime.now()
            })

        # Update cash
        db.session.execute(
            text("UPDATE users SET cash = :cash  WHERE id = :user_id"), {
                "cash": cash[0]["cash"] - total_price,
                "user_id": session["user_id"]
            })

        # Commit the transaction
        db.session.commit()

        # Check if in wallet bought stock exists; if no: insert new entry to wallet; if yes: update wallet
        wallet = db.session.execute(
            text(
                "SELECT * FROM wallet WHERE user_id = :user_id AND symbol = :symbol"
            ), {
                "user_id": session["user_id"],
                "symbol": stock["symbol"]
            })
        wallet = wallet.mappings().all()

        if len(wallet) == 0:
            db.session.execute(
                text(
                    "INSERT INTO wallet (user_id, name, symbol, shares) VALUES (:user_id, :name, :symbol, :shares)"
                ), {
                    "user_id": session["user_id"],
                    "name": stock["name"],
                    "symbol": stock["symbol"],
                    "shares": int(shares)
                })
        else:
            db.session.execute(
                text(
                    "UPDATE wallet SET shares = :shares WHERE user_id = :user_id AND symbol = :symbol"
                ), {
                    "shares": wallet[0]["shares"] + int(shares),
                    "user_id": session["user_id"],
                    "symbol": stock["symbol"]
                })

        # Commit the transaction
        db.session.commit()

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    transactions = db.session.execute(
        text("SELECT * FROM transactions WHERE user_id = :user_id"), {
            "user_id": session["user_id"]
        }).mappings().all()

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Check if captcha was submitted
        token = request.form.get('h-captcha-response')
        if not token:
            return apology("You must complete the captcha", 400)

        # Verify the token with hCaptcha's API
        response = requests.post('https://hcaptcha.com/siteverify',
                                 data={
                                     'secret': HCAPTCHA_SECRET_KEY,
                                     'sitekey': HCAPTCHA_SITE_KEY,
                                     'response': token
                                 })
        result = response.json()

        if result["success"] == False:
            return apology("Captcha verification failed", 400)

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("You must enter the username.", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("You must provide a password.", 403)

        # Query database for username
        rows = db.session.execute(
            text("SELECT * FROM users WHERE username = :username"),
            {"username": request.form.get("username")})
        rows = rows.mappings().all()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
                rows[0]["hash"], request.form.get("password")):
            return apology("Invalid username and/or password.", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html", site_key=HCAPTCHA_SITE_KEY)


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

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("You must provide a symbol.", 400)

        # Check if proper symbol was submitted
        if not lookup(request.form.get("symbol")):
            return apology(
                "Invalid stock symbol. Use the search function to look for suitable symbols.",
                400)

        # lookup for symbol and send result to template
        stock = lookup(request.form.get("symbol"))
        return render_template("quoted.html", stock=stock)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Check if captcha was submitted
        token = request.form.get('h-captcha-response')
        if not token:
            return apology("You must complete the captcha", 400)

        # Verify the token with hCaptcha's API
        response = requests.post('https://hcaptcha.com/siteverify',
                                 data={
                                     'secret': HCAPTCHA_SECRET_KEY,
                                     'sitekey': HCAPTCHA_SITE_KEY,
                                     'response': token
                                 })
        result = response.json()

        if result["success"] == False:
            return apology("Captcha verification failed", 400)

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("You must enter the username.", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("You must provide a password.", 400)

        # Ensure passwords are the same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords are not the same.", 400)

        # Query database for username
        rows = db.session.execute(
            text("SELECT * FROM users WHERE username = :username"),
            {"username": request.form.get("username")})
        rows = rows.mappings().all()

        # Check if user exists
        if len(rows) != 0:
            return apology("User already exists.", 400)

        # Insert new user and pasword hash to database
        db.session.execute(
            text("INSERT INTO users (username, hash) VALUES (:username, :hash)"
                 ),
            {
                "username": request.form.get("username"),
                "hash": generate_password_hash(request.form.get("password"))
            })

        # Commit the transaction
        db.session.commit()

        # login user
        rows = db.session.execute(
            text("SELECT * FROM users WHERE username = :username"), {
                "username": request.form.get("username")
            }).mappings().all()
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html", site_key=HCAPTCHA_SITE_KEY)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Retrieve values from the form
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        # Ensure symbol was submitted
        if not symbol:
            return apology("You must provide a symbol.", 400)

        # Retrieve the user's wallet data for the specified stock symbol
        wallet = db.session.execute(
            text(
                "SELECT name, symbol, shares FROM wallet WHERE user_id = :user_id AND symbol = :symbol"
            ), {
                "user_id": session["user_id"],
                "symbol": symbol
            }).mappings().all()

        # ENSURE user have that stock
        if len(wallet) == 0:
            return apology("You don't own that stock.", 400)

        # Ensure share was submitted
        if not shares:
            return apology("You must provide shares.", 400)

        # Check if number was submited
        try:
            int(shares)
        except:
            return apology("The number of shares must be an integer.", 400)

        # Check if positiv integer was submited
        if int(shares) <= 0:
            return apology("The number of shares must be a positive integer.",
                           400)

        #
        if int(shares) > wallet[0]["shares"]:
            return apology("You don't own that many stock.", 400)

        # Check current stock price
        price = lookup(request.form.get("symbol"))["price"]

        # Updating database
        # Add transaction
        db.session.execute(
            text(
                "INSERT INTO transactions (user_id, name, symbol, type, price, shares, date) VALUES (:user_id, :name, :symbol, :type, :price, :shares, :date)"
            ), {
                "user_id": session["user_id"],
                "name": wallet[0]["name"],
                "symbol": wallet[0]["symbol"],
                "type": "sell",
                "price": price,
                "shares": int(shares),
                "date": datetime.now()
            })

        # Commit the transaction
        db.session.commit()

        # Fetch the current cash value for the user
        cash = db.session.execute(
            text("SELECT cash FROM users WHERE id = :user_id"), {
                "user_id": session["user_id"]
            }).mappings().all()

        # Calculate the total price
        total_price = price * int(shares)

        # Update the user's cash value
        db.session.execute(
            text("UPDATE users SET cash = :new_cash WHERE id = :user_id"), {
                "new_cash": cash[0]["cash"] + total_price,
                "user_id": session["user_id"]
            })

        # Update the shares in the wallet
        db.session.execute(
            text(
                "UPDATE wallet SET shares = :shares WHERE user_id = :user_id AND symbol = :symbol"
            ), {
                "shares": wallet[0]["shares"] - int(shares),
                "user_id": session["user_id"],
                "symbol": symbol
            })

        # Commit the transaction
        db.session.commit()

        # # Check if any of the stocks are left in the wallet
        wallet = db.session.execute(
            text(
                "SELECT shares FROM wallet WHERE user_id = :user_id AND symbol = :symbol"
            ), {
                "user_id": session["user_id"],
                "symbol": symbol
            }).mappings().all()

        # If shares are zero, delete the stock from the wallet
        if wallet[0]["shares"] == 0:
            db.session.execute(
                text(
                    "DELETE FROM wallet WHERE user_id = :user_id AND symbol = :symbol"
                ), {
                    "user_id": session["user_id"],
                    "symbol": symbol
                })

        # Commit the transaction
        db.session.commit()

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # Fetch symbols from the wallet for the given user_id
        wallet = db.session.execute(
            text("SELECT symbol FROM wallet WHERE user_id = :user_id"), {
                "user_id": session["user_id"]
            }).mappings().all()

        return render_template("sell.html", wallet=wallet)


@app.route("/account")
@login_required
def account():
    """Allow users to use additional functions"""

    # Greet currentlly logged user
    user = db.session.execute(
        text("SELECT username FROM users WHERE id = :id"), {
            "id": session["user_id"]
        }).mappings().all()

    return render_template("account.html", user=user)


@app.route("/cash", methods=["POST"])
@login_required
def cash():
    """Allow users to add more cash to their account """

    deposit = request.form.get("cash")

    # Ensure cash was submitted
    if not deposit:
        return apology("You must provide cash.", 400)

    # Check if number was submited
    try:
        int(deposit)
    except:
        return apology("Cash must be integer.", 400)

    # Check if positiv integer was submited
    if int(deposit) <= 0:
        return apology("Cash must be positive integer.", 400)

    # Fetch the current cash value for the user
    cash = db.session.execute(
        text("SELECT cash FROM users WHERE id = :user_id"), {
            "user_id": session["user_id"]
        }).mappings().all()

    # Update the user's cash value
    db.session.execute(
        text("UPDATE users SET cash = :new_cash WHERE id = :user_id"), {
            "new_cash": cash[0]["cash"] + int(deposit),
            "user_id": session["user_id"]
        })

    # Commit the transaction
    db.session.commit()

    # Redirect user to home page
    return redirect("/")


@app.route("/search", methods=["GET", "POST"])
@login_required
def test():

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("You must provide a symbol.", 400)

        # lookup for symbol and send result to template
        search_result = search(request.form.get("symbol"))
        return render_template("searched.html", search_result=search_result)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("search.html")


@app.route("/password_change", methods=["POST"])
@login_required
def password_change():
    """Allow users to change thier password """

    # Ensure old password was submitted
    if not request.form.get("password"):
        return apology("You must provide a password.", 400)

    # Ensure new password was submitted
    if not request.form.get("newpassword"):
        return apology("You must provide a new password.", 400)

    # Ensure passwords are the same
    elif request.form.get("newpassword") != request.form.get("confirmation"):
        return apology("Passwords are not the same.", 400)

    # Query database for username
    user = db.session.execute(text("SELECT * FROM users WHERE id = :id"), {
        "id": session["user_id"]
    }).mappings().all()

    # Ensure password is correct
    if not check_password_hash(user[0]["hash"], request.form.get("password")):
        return apology("Invalid password.", 403)

    # Update pasword hash in database
    db.session.execute(
        text("UPDATE users SET hash = :hash WHERE id = :id"), {
            "id": session["user_id"],
            "hash": generate_password_hash(request.form.get("newpassword"))
        })

    # Commit the transaction
    db.session.commit()

    # Redirect user to home page
    return redirect("/")
