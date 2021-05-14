from flask_caching import Cache

"""
Define this extension instance here in its own file so it can be imported all around my app
"""
config={'CACHE_TYPE': 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT' : 900}
cache = Cache(config=config)

