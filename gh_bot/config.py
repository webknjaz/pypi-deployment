#! /usr/bin/env python

from pathlib import Path
from warnings import catch_warnings

from envparse import Env


with catch_warnings(record=True):
    #Env.read_envfile(Path('..'))
    Env.read_envfile()

env = Env()


server_port = env('PORT', cast=int, default=8080)

app_id = env('GH_APP_ID', cast=int)
install_id = env('GH_INSTALL_ID', cast=int)
private_key_path = env('GH_PRIVATE_KEY_PATH')
private_key = env('GH_PRIVATE_KEY', default=None)

# oauth:
client_id = env('GH_OAUTH_CLIENT_ID')
client_secret = env('GH_OAUTH_CLIENT_SECRET')

app_domain = env('GH_APP_DOMAIN', default=None) or f"{env('NGROK_TUN_SLUG')}.ngrok.io"
gh_auth_url = f'https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri=https%3A%2F%2F{app_domain}%2Flogin%2Foauth'
