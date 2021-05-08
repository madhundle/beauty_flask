import os

from flask import Flask

def create_app(test_config=None):
    """
    Application factory function
    """
    # create and configure app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'beauty_flask.sqlite')
    )

    if test_config is None:
        # If not testing, load the instance config if it exists
        app.config.from_pyfile('config.py', silent=True)
    else:
        # If testing config passed in, load it
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # import db functionality
    from . import db
    db.init_app(app)

    # import admin functionality
    from . import admin
    app.register_blueprint(admin.bp)

    # import base site functionality
    from . import site
    app.register_blueprint(site.bp)
    # the 'site' blueprint does not have a url_prefix, so the 'index' view is at '/'
    app.add_url_rule('/', endpoint='index')

    return app


