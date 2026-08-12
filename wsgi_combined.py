"""Combined WSGI entry point for a single-service test deployment.

Runs both sites in one process under one host, so they keep sharing the
same SQLite file the way they do when you run them separately on your own
computer. Mount: customer site at "/", seller portal at "/seller".

For real production, deploy customer/app.py and seller/app.py as two
separate services pointed at a shared hosted database instead — see the
README's "Going live" section.
"""
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from customer.app import app as customer_app
from seller.app import app as seller_app

application = DispatcherMiddleware(customer_app, {
    "/seller": seller_app,
})
