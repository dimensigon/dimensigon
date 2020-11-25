from requests.auth import AuthBase


class HTTPBearerAuth(AuthBase):
    def __init__(self, token):
        self.token = token

    def __eq__(self, other):
        return self.token == getattr(other, 'token', None)

    def __ne__(self, other):
        return not self == other

    def __call__(self, r):
        if hasattr(r, 'headers'):
            r.headers.update(self.header)
        else:
            r['headers'].update(self.header)
            r.pop('auth', None)
        return r

    @property
    def header(self):
        return {'Authorization': str(self)}

    def __str__(self):
        return 'Bearer ' + self.token
