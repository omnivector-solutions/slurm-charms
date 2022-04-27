"""Omnivector wrapper for etcd3gw."""
# heavily copied from Calico project

import logging

from etcd3gw.client import Etcd3Client
from etcd3gw.exceptions import Etcd3Exception

logger = logging.getLogger(__name__)


class Etcd3AuthClient(Etcd3Client):
    """Handle etcd3 requests with auth."""
    def __init__(self, host='localhost', port=2379, protocol="http",
                 ca_cert=None, cert_key=None, cert_cert=None, timeout=None,
                 username=None, password=None, api_path="/v3/"):
        """Initialize class."""
        super(Etcd3AuthClient, self).__init__(host=host,
                                              port=port,
                                              protocol=protocol,
                                              ca_cert=ca_cert,
                                              cert_key=cert_key,
                                              cert_cert=cert_cert,
                                              timeout=timeout,
                                              api_path=api_path)
        self.username = username
        self.password = password

    def authenticate(self):
        """Authenticate the client."""
        # When authenticating, there mustn't be an Authorization
        # header with an old token, or else etcd responds with
        # "Unauthorized: invalid auth token".  So remove any existing
        # Authorization header.
        if 'Authorization' in self.session.headers:
            del self.session.headers['Authorization']

        # Send authenticate request.  If this raises an exception,
        # e.g. because of a connectivity issue to the etcd server,
        # it's OK for that to bubble up and be handled in the code
        # that called post.
        response = super(Etcd3AuthClient, self).post(
            self.get_url('/auth/authenticate'),
            json={"name": self.username, "password": self.password}
        )

        # Add Authorization header with the received token to the
        # underlying requests session.  This covers all subsequent
        # requests, and is needed in particular for watches, because
        # the watch code does not use client.post and so could not be
        # covered by adding a header to kwargs in the following post
        # method.
        self.session.headers['Authorization'] = response['token']

    def post(self, *args, **kwargs):
        """Wrap the internal post function with authentication."""
        try:
            # Try the post. If no authentication is needed, or if an
            # Authorization token has been added to the session's
            # headers, and is still valid, this should succeed.
            return super(Etcd3AuthClient, self).post(*args, **kwargs)
        except Etcd3Exception as e:
            if self.username and self.password:
                # Etcd auth credentials are configured, so assume the
                # problem might be that we need to authenticate or
                # re-authenticate.
                logger.info("## etcd: Might need to (re)authenticate: %r:\n%s",
                            e, e.detail_text)

                # Authenticate and then reissue the request.
                self.authenticate()
                return super(Etcd3AuthClient, self).post(*args, **kwargs)

            raise
