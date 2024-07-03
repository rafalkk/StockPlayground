import os
import requests
import urllib.parse
from datetime import datetime

from flask import redirect, render_template, request, session
from functools import wraps


def check_env_vars(vars_list):
    # Create a list of environment variables that are not set
    missing_vars = [var for var in vars_list if not os.environ.get(var)]

    # If the list is non-empty, raise a RuntimeError
    if missing_vars:
        raise RuntimeError(
            f"Missing environment variables: {', '.join(missing_vars)}")


def apology(message, code=400):
    """Render message as an apology to user."""

    return render_template("error.html", top=code, bottom=message), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        API_KEY = os.environ.get("API_KEY")
        # https://finnhub.io/docs/api/company-profile2
        profile2_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={API_KEY}"

        # https://finnhub.io/docs/api/quote
        quote_url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"

        profile2_response = requests.get(profile2_url)
        profile2_response.raise_for_status()

        quote_response = requests.get(quote_url)
        quote_response.raise_for_status()

    except requests.RequestException:
        return None

    # Parse response
    try:
        profile2 = profile2_response.json()
        quote = quote_response.json()
        return {
            "name": profile2["name"],
            "price": float(quote["c"]),
            "symbol": profile2["ticker"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def search(symbol):
    """Search for best-matching symbols"""
    """US market only"""

    # Contact API
    try:
        API_KEY = os.environ.get("API_KEY")

        # https://finnhub.io/docs/api/symbol-search
        search_url = f"https://finnhub.io/api/v1/search?q={symbol}&token={API_KEY}"

        search_response = requests.get(search_url)
        search_response.raise_for_status()

        # https://finnhub.io/docs/api/stock-symbols
        stock_symbols_url = f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={API_KEY}"

        stock_symbols_response = requests.get(stock_symbols_url)
        stock_symbols_response.raise_for_status()

    except requests.RequestException:
        return None

    # Parse response
    try:
        search = search_response.json()
        stock_symbols = stock_symbols_response.json()

        # Extract symbols from stock_symbols
        stock_symbols_list = [symbol["symbol"] for symbol in stock_symbols]

        # Filter search results to only include symbols that are in stock_symbols_list
        filtered_search = [
            item for item in search["result"]
            if item["symbol"] in stock_symbols_list
        ]

        return filtered_search

    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def percent(value):
    """Format value as percent."""
    return f"{value:,.2f} %"


def format_date(date_string):
    """Format datetime object to a string with a specific format."""
    date = datetime.fromisoformat(date_string)
    return f"{date.strftime('%Y-%m-%d')}&nbsp; &nbsp;{date.strftime('%H:%M:%S')}"
