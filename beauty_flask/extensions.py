from flask_caching import Cache
from flask_mail import Mail

"""
Define extension instances here in own file so they can be imported all around the app
"""
# Caching
#config = {'CACHE_TYPE': 'SimpleCache',
#          'CACHE_DEFAULT_TIMEOUT' : 900}
#cache = Cache(config=config)
cache = Cache()

# Mail
#config = {'MAIL_DEFAULT_SENDER': 'no-reply@stephaniebeauty.com'}
#mail = Mail(config=config)
mail = Mail()
