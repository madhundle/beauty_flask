import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from beauty_flask.db import get_db

import datetime
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import json
 
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

@bp.route('/logout', methods=('GET', 'POST'))
#@login_required
def logout():
    """
    Log the current admin out
    """
    session.clear()
    #session.modified = True # make Flask send the updated session cookie to the client
    return render_template('admin/logout.html')


@bp.route('/dash', methods=('GET', 'POST'))
@login_required
def dash():
    """
    Create a 'dash' view for the 'admin' blueprint
    Associate the '/dash' URL with this 'login' view function
    """
    # immutable tuples to maintain sorting
    days = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')
    timeblocks = ('0800', '0830', '0900', '0930', '1000', '1030', '1100', '1130', '1200', '1230', '1300', '1330', '1400', '1430', '1500', '1530', '1600', '1630', '1700', '1730', '1800', '1830', '1900', '1930', '2000')
    
    avail = {d:{t:False for t in timeblocks} for d in days} # initialize empty schedule
    if os.path.exists('instance/availability.json'): # load saved schedule
        with open('instance/availability.json', 'r') as f:
            avail = json.load(f)
 
    if request.method == "POST" and request.form['Edit']=='Edit':
#        flash(request)
#        flash(request.form)
        return render_template('admin/dash.html', edit=True, days=days, timeblocks=timeblocks, avail=avail)
    
    elif request.method == "POST" and request.form['Edit']=='Save':
#        flash(request)
#        flash(request.form)
        for item in request.form.items(): # iterate over items, not just the keys
            # request.form is an ImmutableMultiDict with entries e.g. ([('Sun_0800', 'True'), ('Mon_0800', 'False')
            if item[0] == 'Edit': 
                continue
            day, time = item[0].split('_')
            avail[day][time] = json.loads(item[1].lower()) # item[1] is str 'True'|'False'; convert to bool
#        flash(avail)
        with open('instance/availability.json', 'w') as f:
            json.dump(avail, f)

    return render_template('admin/dash.html', edit=False, days=days, timeblocks=timeblocks, avail=avail)



