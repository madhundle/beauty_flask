import os

from flask import Flask

# Extension defined in separate file for use with application factory function
#from .cache import cache


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
    # the 'site' blueprint does not have a url_prefix and the 'index' view routes just '/'
    # so explicitly create this url rule so 'index' works as an endpoint name as well as 'site.index'
    # (i.e. url_for('index') and url_for('site.index') will now both work)
    app.add_url_rule('/', endpoint='index')

    # Extensions
    # import cache functionality
    from .cache import cache
#    app.config.from_mapping(CACHE_TYPE='SimpleCache')
    cache.init_app(app)
#    cache.cache_type = app.config['CACHE_TYPE']


    return app


