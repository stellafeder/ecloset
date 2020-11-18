import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
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
db = SQL("postgres://tlyzytnpqeyevt:29b9b160dfdcfd24efbda48f4c1ef0399e975e5366063d8b6728e1ae0ea2b5fa@ec2-34-231-56-78.compute-1.amazonaws.com:5432/dhnp7orj2v96k")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""

    # NOTE: I included a cash-adding form to this page

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":

        # Show HTML table summarizing stock holdings of current user
        stocks = db.execute("SELECT symbol, SUM(shares) FROM purchases WHERE user_id = ? GROUP BY symbol", session["user_id"])

        # Iterate through the list of stocks and add its price, name, and total value to its respective dictionary
        for stock in stocks:
            stock["price"] = lookup(stock['symbol'])['price']
            stock["name"] = lookup(stock['symbol'])['name']
            stock["total"] = stock["price"] * stock["SUM(shares)"]

        # Find current user's cash balance
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

        # Render HTML
        return render_template("index.html", stocks = stocks, cash = cash)

    # User reached route via POST (as by submitting a form via POST)
    else:

        # Ensure cash is entered
        if not request.form.get("cash"):
            return apology("please enter cash amount", 400)

        # Ensure cash is a number
        try:
            requested_cash = float(request.form.get("cash"))
        except ValueError:
            return apology("cash must be number", 400)

        # Ensure cash is positive
        if requested_cash <= 0:
            return apology("cash must be positive", 400)

        # Add requested cash to current cash
        current_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", int(current_cash) + int(requested_cash), session["user_id"])

        # Refresh Index page
        return redirect("/")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("buy.html")

    # User reached route via POST (as by submitting a form via POST)
    else:

        # Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("please enter stock symbol", 400)

        # Ensure stock symbol is a string
        try:
            unformatted_symbol = str(request.form.get("symbol"))
        except ValueError:
            return apology("cash must be number", 400)

        # Cast symbol to uppercase
        try:
            symbol = unformatted_symbol.upper()
        except ValueError:
            return apology("could not convert unformatted string to upper", 400)

        # Ensure stock exists
        if not lookup(symbol):
            return apology("ticker not found", 400)

        # Ensure number of shares was submitted
        if not request.form.get("shares"):
            return apology("please enter positive integer number of shares", 400)

        # Ensure number of shares is positive integer
        try:
            shares = float(request.form.get("shares"))
        except ValueError:
            return apology("cash must be number", 400)

        if not shares.is_integer():
            return apology("shares must be integer", 400)

        if shares < 0:
            return apology("shares must be positive", 400)

        # Find how much purchase would cost
        expenditure = lookup(symbol)['price'] * shares

        # Select how much cash current user has
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"]) [0]["cash"]

        # Ensure user can afford purchase
        if cash < expenditure:
            return apology("cannot afford this purchase", 400)

        # Insert purchases into table
        db.execute("INSERT INTO purchases (user_id, symbol, shares) VALUES (?, ?, ?)", session["user_id"], symbol, shares)

        # Update person's cash value
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - expenditure, session["user_id"])

        # Redirect to History page
        return redirect("/history")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Query list of dictionaries summarizing current user's transactions
    transactions = db.execute("SELECT symbol, shares, datetime FROM purchases WHERE user_id = ? ORDER BY datetime DESC", session["user_id"])

    # Iterate through the list of transactions and add its price and purchase time to its dictionary
    for transaction in transactions:
        transaction["price"] = lookup(transaction['symbol'])['price']

    # Render HTML
    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

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
    """Get stock quote."""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("quote.html")

    # User reached route via POST (as by submitting a form via POST)
    else:

        # Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("please enter stock symbol", 400)

        # Ensure stock symbol is a string
        try:
            symbol = str(request.form.get("symbol"))
        except ValueError:
            return apology("cash must be number", 400)

        # Ensure stock exists
        if not lookup(symbol):
            return apology("ticker not found", 400)

        # Return stock price
        return render_template("quoted.html", stock = lookup(symbol))

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("register.html")

    # User reached route via POST (as by submitting a form via POST)
    else:

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Make sure username hasn't been taken
        match = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(match) != 0:
            return apology("username taken", 400)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password confirmation was submitted
        if not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # Ensure password matches password confirmation
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("password must match password confirmation", 400)

        # Define variables for better readability
        username = request.form.get("username")
        password = request.form.get("password")

        # Hash password
        p_hash = generate_password_hash(password)

        # Insert user into database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, p_hash)

        # Log user in automatically
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        session["user_id"] = rows[0]["id"]

        # Redirect to homepage
        return redirect ("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":

        # Select stock holdings of current user
        stocks = db.execute("SELECT symbol FROM purchases WHERE user_id = ? GROUP BY symbol", session["user_id"])

        # Render template
        return render_template("sell.html", stocks = stocks)

    # User reached route via POST (as by submitting a form via POST)
    else:

        # Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("please enter stock symbol", 400)

        # Ensure stock symbol is a string
        try:
            symbol = str(request.form.get("symbol"))
        except ValueError:
            return apology("cash must be number", 400)

        # Ensure stock exists
        if not lookup(symbol):
            return apology("ticker not found", 400)

        # Ensure number of shares was submitted
        if not request.form.get("shares"):
            return apology("please enter positive integer number of shares", 400)

        # Ensure number of shares is positive integer
        try:
            shares = float(request.form.get("shares"))
        except ValueError:
            return apology("cash must be number", 400)

        if not shares.is_integer():
            return apology("shares must be integer", 400)

        if shares < 0:
            return apology("shares must be positive", 400)

        # Ensure user has ever purchased this stock

        # Create list of stocks user has purchased
        stock_list = []
        dictionaries = db.execute("SELECT symbol FROM purchases WHERE user_id = ?", session["user_id"])
        for item in dictionaries:
            stock_list.append(item["symbol"])

        # Ensure requested stock has been purchased by the user
        if request.form.get("symbol") not in stock_list:
            return apology("you have never owned this stock", 400)

        # Find how much of this stock user owns currently
        total = db.execute("SELECT SUM(shares) FROM purchases WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)[0]["SUM(shares)"]
        print(total)
        print(shares) # AAAAAAAADH

        # Ensure user owns enough shares to sell desired quantity
        if shares > total:
            return apology("attempted to sell too many shares", 400)

        # Update user's cash amount
        sale_value = lookup(symbol)['price'] * shares
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + sale_value, session["user_id"])

        # Add sale to purchases record
        db.execute("INSERT INTO purchases (user_id, symbol, shares) VALUES (?, ?, ?)", session["user_id"], symbol, -shares)

        # Redirect to History page
        return redirect("/history")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
