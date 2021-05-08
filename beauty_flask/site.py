from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
# from werkzeug.exceptions import abort

# from flaskr.auth import login_required
# from flaskr.db import get_db

bp = Blueprint('site', __name__)

@bp.route('/')
def index():
    return render_template('site/index.html')

@bp.route('/book')
def book():
    return render_template('site/book.html')

@bp.route('/pay')
def pay():
    return render_template('site/pay.html')

