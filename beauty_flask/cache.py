from flask_caching import Cache

"""
Define this extension instance here in its own file so it can be imported all around my app
"""
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})

