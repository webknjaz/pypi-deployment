#! /usr/bin/env python

from pprint import pprint
import textwrap
from urllib.parse import parse_qsl
import uuid

import cherrypy

import requests

from .config import (
    # oauth:
    client_id, client_secret,
    gh_auth_url_tmpl,
)


class GitHubLogin:
    @cherrypy.expose
    def index(self):
        try:
            cherrypy.session['gh_access_token']
            raise cherrypy.HTTPRedirect('/list-repos')
        except KeyError:
            cherrypy.session['gh_oauth_state'] = (
                'secret-' +
                str(uuid.uuid1()).rpartition('-')[-1]
            )
            fqdn = cherrypy.request.headers['Host']
            raise cherrypy.HTTPRedirect(
                gh_auth_url_tmpl.format(app_domain=fqdn) +
                '&state=' +
                cherrypy.session['gh_oauth_state']
            )

    @cherrypy.expose
    def oauth(self, code, state):
        print(code, state)
        try:
            if state != cherrypy.session['gh_oauth_state']:
                raise cherrypy.HTTPError(
                    401,
                    'OAuth state is invalid. Try '
                    '<a href="/login">login</a> again.',
                )
        except KeyError:
            raise cherrypy.HTTPError(
                401,
                'Go to <a href="/">Home</a> for login.',
            )

        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
        }
        access_token_resp = requests.post(
            'https://github.com/login/oauth/access_token',
            data=data,
        )
        #print(access_token_resp)
        access_token = dict(
            parse_qsl(access_token_resp.text)
        )['access_token']
        print('access token:')
        print(access_token)
        gh_user = requests.get(
            f'https://api.github.com/user?access_token={access_token}'
        ).json()
        print('gh user:')
        pprint(gh_user)
        user_installations_obj = requests.get(f'https://api.github.com/user/installations?access_token={access_token}', headers={'Accept': 'application/vnd.github.machine-man-preview+json'}).json()
        print('user installations obj:')
        pprint(user_installations_obj)
        installations = user_installations_obj['installations']
        pprint(installations)
        cherrypy.session['gh_login'] = gh_user['login']
        cherrypy.session['gh_access_token'] = access_token
        cherrypy.session['gh_installations'] = installations
        #import ipdb; ipdb.set_trace()
        #gh_client = Github(access_token)
        #gh_user = gh_client.get_user()
        #print(gh_user)
        #print(gh_user._requester)
        #print(gh_user._requester.requestJsonAndCheck('POST', gh_user.url))
        #return code, '<br>', state, f'{gh_user.login} {gh_user.name}'
        #return code, '<br>', state, f'{inst_id}'
        return textwrap.dedent(f'''
            Hi {cherrypy.session["gh_login"]},<br>
            You have enabled {len(installations)} installations<br>
            <a href="https://github.com/apps/dobby-ans/installations/new">
                Installs some more
            </a><br>
            <a href="/list-repos">List repos</a>.
        '''.strip())
