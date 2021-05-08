import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    """
    Connect to the database if needed and get the contents
    """
    # g is a special object unique for each request
    # current_app is a special object pointing to the Flask app handling the request
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    """
    If there is an open connection to the database, close it
    """
    # check if a connection was created
    db = g.pop('db', None)

    # if so, close it
    if db is not None:
        db.close()
    return

def init_db():
    """
    Initialize the SQL database
    """
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))
    return

# define a command line command 'init-db' to call this function and show success message to user
@click.command('init-db') 
@with_appcontext
def init_db_command():
    """
    Initialize the database
    """
    # Clear existing data if present and create new tables
    init_db()
    click.echo('Initialized the database.')
    return

def init_app(app):
    """
    Register these functions with the application instance so they get used
    """
    app.teardown_appcontext(close_db) # tell Flask to call this when cleaning up after returning response
    app.cli.add_command(init_db_command) # adds a new command that can be called with the `flask` command
    return


