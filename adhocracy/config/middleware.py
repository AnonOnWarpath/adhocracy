"""Pylons middleware initialization"""
from beaker.middleware import CacheMiddleware, SessionMiddleware
from paste.cascade import Cascade
from paste.registry import RegistryManager
from paste.urlparser import StaticURLParser
from paste.deploy.converters import asbool
from pylons import config
from pylons.middleware import ErrorHandler, StatusCodeRedirect
from pylons.wsgiapp import PylonsApp
from routes.middleware import RoutesMiddleware

from adhocracy.lib.auth.authentication import setup_auth
from adhocracy.lib.instance import setup_discriminator
from adhocracy.lib.util import get_site_path
from adhocracy.config.environment import load_environment


def make_app(global_conf, full_stack=True, static_files=True, **app_conf):
    """Create a Pylons WSGI application and return it

    ``global_conf``
        The inherited configuration for this application. Normally from
        the [DEFAULT] section of the Paste ini file.

    ``full_stack``
        Whether this application provides a full WSGI stack (by default,
        meaning it handles its own exceptions and errors). Disable
        full_stack when this application is "managed" by another WSGI
        middleware.

    ``static_files``
        Whether this application serves its own static files; disable
        when another web server is responsible for serving them.

    ``app_conf``
        The application's local configuration. Normally specified in
        the [app:<name>] section of the Paste ini file (where <name>
        defaults to main).

    """

    debug = asbool(config['debug'])

    # Configure the Pylons environment
    load_environment(global_conf, app_conf)

    # The Pylons WSGI app
    app = PylonsApp()

    # Routing/Session/Cache Middleware
    app = RoutesMiddleware(app, config['routes.map'])
    app = SessionMiddleware(app, config)
    app = CacheMiddleware(app, config)

    #app = make_profile_middleware(app, config, log_filename='profile.log.tmp')

    # CUSTOM MIDDLEWARE HERE (filtered by error handling middlewares)
    app = setup_auth(app, config)
    app = setup_discriminator(app, config)

    if asbool(full_stack):
        # Handle Python exceptions
        app = ErrorHandler(app, global_conf, **config['pylons.errorware'])

    # Display error documents for 401, 403, 404 status codes (and
    # 500 when debug is disabled)
    if debug:
        app = StatusCodeRedirect(app)
    else:
        app = StatusCodeRedirect(app, [400, 401, 403, 404, 500])

    # Establish the Registry for this application
    app = RegistryManager(app)

    if asbool(static_files):
        cache_age = int(config.get('adhocracy.static.age', 7200))
        # Serve static files
        overlay_app = StaticURLParser(get_site_path('static'),
            cache_max_age=None if debug else cache_age)
        static_app = StaticURLParser(config['pylons.paths']['static_files'],
            cache_max_age=None if debug else cache_age)
        app = Cascade([overlay_app, static_app, app])

    return app
