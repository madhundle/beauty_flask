import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from beauty_flask.db import get_db

# Create a blueprint named 'admin'
bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/login', methods=('GET', 'POST'))
def login():
    """
    Create a 'login' view for the 'admin' blueprint
    Associate the '/login' URL with this 'login' view function
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM admin WHERE username = ?', (username,)
        ).fetchone()

        if user is None:
            error = 'Invalid username.'
        elif not check_password_hash(user['password'], password):
            error = 'Invalid password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('admin.dash'))

        flash(error) # store error message that the template can show when rendering

    return render_template('admin/login.html')


@bp.before_app_request # Registers a function that runs before the view function
def load_logged_in_user():
    """
    If a user is logged in, load their information and store in g.user so it's available to all views 
    """
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM admin WHERE id = ?', (user_id,)
        ).fetchone()

def login_required(view):
    """
    This decorator for other views will check if a user is logged in and redirect to the login page otherwise
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('admin.login'))

        return view(**kwargs)

    return wrapped_view

@bp.route('/dash', methods=('GET', 'POST'))
@login_required
def dash():
    """
    Create a 'dash' view for the 'admin' blueprint
    Associate the '/dash' URL with this 'login' view function
    """
    return render_template('admin/dash.html')

@bp.route('/logout', methods=('GET', 'POST'))
#@login_required
def logout():
    """
    Log the current admin out
    """
    session.clear()
    #session.modified = True # make Flask send the updated session cookie to the client
    return render_template('admin/logout.html')
    #return redirect(url_for('admin.logout'))

