import requests
import simplejson as json  # http://stackoverflow.com/questions/30289647/rauth-with-google-provider-and-python3
from flask import current_app, redirect, request, url_for
from rauth import OAuth2Service


# http://blog.miguelgrinberg.com/post/oauth-authentication-with-flask

class OAuthSignIn(object):
    providers = None

    def __init__(self, provider_name):
        self.provider_name = provider_name
        credentials = current_app.config['OAUTH_CREDENTIALS'][provider_name]
        self.consumer_id = credentials['id']
        self.consumer_secret = credentials['secret']

    def authorize(self):
        pass

    def callback(self):
        pass

    def get_callback_url(self):
        return url_for('oauth_callback', provider=self.provider_name, _external=True)

    @classmethod
    def get_provider(cls, provider_name):
        if cls.providers is None:
            cls.providers = {}
            for provider_class in cls.__subclasses__():
                provider = provider_class()
                cls.providers[provider.provider_name] = provider
        return cls.providers[provider_name]


class GoogleSignIn(OAuthSignIn):
    def __init__(self):
        super(GoogleSignIn, self).__init__('google')
        googleinfo = requests.get('https://accounts.google.com/.well-known/openid-configuration')
        google_params = googleinfo.json()
        self.service = OAuth2Service(
            name='google',
            client_id=self.consumer_id,
            client_secret=self.consumer_secret,
            authorize_url=google_params.get('authorization_endpoint'),
            base_url=google_params.get('userinfo_endpoint'),
            access_token_url=google_params.get('token_endpoint')
        )

    def authorize(self):
        return redirect(self.service.get_authorize_url(
            scope='email',
            response_type='code',
            redirect_uri=self.get_callback_url())
        )

    def callback(self):
        if 'code' not in request.args:
            return None, None

        oauth_session = self.service.get_auth_session(
            data={'code': request.args['code'],
                  'grant_type': 'authorization_code',
                  'redirect_uri': self.get_callback_url()},
            decoder=json.loads
            # decoder=lambda b: json.loads(str(b))
            # https://github.com/litl/rauth/issues/145
            # "passing a urllib request object to Flask's JSON parse function breaks on Python 3"
            # http://lucumr.pocoo.org/2014/1/5/unicode-in-2-and-3/
        )
        me = oauth_session.get('').json()
        return (me['name'],
                me['email'])
