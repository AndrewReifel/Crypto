from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
#test push


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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    if request.method == "GET":
        # get cash info from users database
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        grandtotal = cash[0]["cash"]

        # obtain stock info from portoflio database
        stocks = db.execute("SELECT symbol, shares FROM portfolio WHERE id = :id", id=session["user_id"])

        # for every stock in the user proftfolio, assign dict key for use in html/jinja

        for stock in stocks:
            symbol = str(stock["symbol"])
            shares = int(stock["shares"])
            name = ""
            price = ""
            total = ""
            quote = lookup(symbol)
            stock["name"] = quote["name"]
            stock["price"] = "{:.2f}".format(quote["price"])
            stock["total"] = "{:.2f}".format(quote["price"] * shares)
            stock["grandtotal"] = quote["price"] * shares
            grandtotal += stock["grandtotal"]

        # format grandtotal to force 2 decimal spots
        grandtotal = "{:.2f}".format(grandtotal)

        # render index page with some given values
        return render_template("index.html", stocks=stocks, cash=cash, grandtotal=grandtotal)

    # Change password
    else:
        if not request.form.get("password_1") or request.form.get("password_2"):
            return apology("must provide passwords", 403)
        elif request.form.get("password_1") != request.form.get("password_2"):
            return apology("passwords are not the same", 403)
        else:
            hash = generate_password_hash(request.form.get("password_1"))
            rows = db.execute("UPDATE users SET hash=:new_hash WHERE id=:id", new_hash=hash, id=session["user_id"])
            return render_template("/changepassword.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # if user reaches route via POST ensure all fields are filled
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("You must provide the symbol and # of shares")

        # use lookup function to get stock info
        quote = lookup(request.form.get("symbol"))

        # ensure validity of form
        if quote == None:
            return apology("invalid symbol")
        if not request.form.get("shares").isdigit():
            return apology("must provide an integer")

        shares = int(request.form.get("shares"))
        price = round(float(quote["price"]), 2)
        if shares < 1:
            return apology("must provide a positive interger of shares")

        # compare users cash amount to total cost of shares
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        cost = round(float(shares * price), 2)

        # return error if not enough cash on hand
        if cost > cash[0]["cash"]:
            return apology("insufficient funds")

        # if sufficent cash available, update users, portfolio, and histroy with the new information
        else:
            db.execute("UPDATE users SET cash = cash - :cost WHERE id = :id", cost=cost, id=session["user_id"])
            db.execute("UPDATE portfolio SET shares = shares + :shares WHERE id = :id AND symbol = :symbol",
                       id=session["user_id"], symbol=quote["symbol"], shares=shares)
            db.execute("INSERT OR IGNORE INTO portfolio (id,symbol,shares) VALUES (:id,:symbol,:shares)",
                       id=session["user_id"], symbol=quote["symbol"], shares=shares)
            db.execute("INSERT INTO history (id,symbol,shares,price,date) VALUES (:id,:symbol,:shares,:price,datetime('now'))",
                       id=session["user_id"], symbol=quote["symbol"], shares=shares, price=price)

        flash('Bought!')
        return redirect(url_for("index"))

    # else if user reached route via get
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # obtain stock info from portfolio database
    history = db.execute("SELECT symbol, shares, price, date FROM history WHERE id = :id ORDER BY date DESC", id=session["user_id"])

    # for every stock in the user's portfolio, assign dict key/values for use in html/jinja
    for transaction in history:
        symbol = transaction["symbol"]
        shares = transaction["shares"]
        price = transaction["price"]
        date = transaction["date"]

    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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

    # if user routed via GET, return the quote page
    if request.method == "GET":
        return render_template("quote.html")

    # if user reached route via POST (such as submitting a form) check that the form is valid
    elif request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Please provide a stock symbol")

        # use lookup func to get current stock info from user entered symbol
        quote = lookup(request.form.get("symbol"))

        # check if stock exists YAHOO
        if quote == None:
            return apology("invalid symbol")

        # if it does, display the info
        else:
            return render_template("quoted.html", name=quote["name"], symbol=quote["symbol"], price=quote["price"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # manipulate the information the user has submitted
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("Please enter username")

        # ensure password was submitted
        if not request.form.get("password"):
            return apology("Please enter password")

        # ensure password confirmation was submitted
        if not request.form.get("confirmation"):
            return apology("Please confirm password")

        # ensure password and confirmation match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Password don't match")

        # store the hash of the password and not the actual password that was typed in
        password = request.form.get("password")
        hash = generate_password_hash(password)

        # username must be a unique field
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                            username=request.form.get("username"), hash=hash)
        if not result:
            return apology("Pick another username")

        # store their id in session to log them in automatically
        user_id = db.execute("SELECT id FROM users WHERE username IS :username", username=request.form.get("username"))
        session['user_id'] = user_id[0]['id']

        # redirect user to home page
        flash('Successfully registered!')
        return redirect(url_for("index"))

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # if user reached route via POST, check if all fields are filled out
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("must provide symbol and number of shares")

        # use lookup func to get info on stocks
        quote = lookup(request.form.get("symbol"))

        # make sure form is valid
        if quote == None:
            return apology("invalid symbol")
        if not request.form.get("shares").isdigit():
            return apology("must provide positive integer")

        # initiate variables to use
        shares = int(request.form.get("shares"))
        stocks = []

        # obtain user stock info from the portfolio database
        stocks = db.execute("SELECT shares FROM portfolio WHERE id = :id AND symbol = :symbol",
                            id=session["user_id"], symbol=quote["symbol"])

        # check that user actually owns enough stock, or any at all

        if stocks == []:
            return apology("you dont own any of this stock")
        if shares > stocks[0]["shares"]:
            return apology("invalid number of shares")

        # calculate price per share and cost of all shares
        price = round(float(quote["price"]), 2)
        cost = round(float(shares * price), 2)

        # update user cash balance in database
        db.execute("UPDATE users SET cash = cash + :cost WHERE id = :id", cost=cost, id=session["user_id"])

        # if leftover shares after sales, update row in db
        if shares < stocks[0]["shares"]:
            db.execute("UPDATE portfolio SET shares=shares - :shares WHERE id = :id AND symbol = :symbol",
                       id=session["user_id"], shares=shares, symbol=quote["symbol"])

        # else if no shares leftover, remove row from portoflio
        elif shares == stocks[0]["shares"]:
            db.execute("DELETE FROM portfolio WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=quote["symbol"])

        db.execute("INSERT INTO history (id,symbol,shares,price,date) VALUES (:id,:symbol,:shares,:price,datetime('now'))",
                   id=session["user_id"], symbol=quote["symbol"], shares=-shares, price=price)

        flash('Sold!')
        return redirect(url_for("index"))
    else:
        Symbols = db.execute(
            "SELECT Symbol as symbol FROM portfolio WHERE id = :user_id GROUP BY Symbol HAVING SUM(Shares) !=0", user_id=session["user_id"])
        return render_template("sell.html", symbols=Symbols)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


app.jinja_env.globals.update(usd=usd)