#! /usr/bin/env python

from pprint import pprint

import cherrypy

import requests

from gh_bot.event_listener import GithubEventDispatcher, GitHubEventHandler
from gh_bot.gh_login import GitHubLogin
from gh_bot.gh import (
    get_github_integration, get_installation_client,
)
from gh_bot.config import (
    server_port,
    app_id,
    install_id, private_key_path,
)


class GitHubApp:
    @cherrypy.expose
    def index(self):
        return '<a href="login">Log in with GitHub</a>'

    @cherrypy.expose
    @cherrypy.tools.sessions()
    def check_repos(self, install_id, repo_slug='webknjaz/.me', head_branch='master', head_sha='HEAD'):
        gh_int = get_github_integration(app_id, private_key_path)
        gh_client = get_installation_client(gh_int, install_id)
        access_token = cherrypy.session['gh_access_token']
        chk_res = requests.post(f'https://api.github.com/repos/{repo_slug}/check-runs?access_token={access_token}', json={'head_branch': head_branch, 'head_sha': head_sha, 'name': 'wk:check:test', 'status': 'completed', 'completed_at': '2018-05-27T00:30:33Z', 'conclusion': 'neutral'}, headers={'Accept': 'application/vnd.github.antiope-preview+json'})
        # import ipdb; ipdb.set_trace()
        return 'OK'

    @cherrypy.expose
    @cherrypy.tools.sessions()
    def list_repos(self, install_id=None):
        installs = map(lambda i: i['id'], cherrypy.session['gh_installations']) if install_id is None else [install_id]
        installs = list(map(int, installs))

        resp = []
        for inst_id in installs:
            resp.append(f'<h3>{inst_id}</h3>')
            resp.append('<ul>')
            gh_int = get_github_integration(app_id, private_key_path)
            gh_client = get_installation_client(gh_int, inst_id)
            rp = gh_client.get_repo('webknjaz/.me')
            headers, data = rp._requester.requestJsonAndCheck(
                "GET",
                f'http://api.github.com/installation/repositories',
                headers={'Accept': 'application/vnd.github.machine-man-preview+json'},
            )
            pprint(data['repositories'][0])
            pprint(data['repositories'][0])
            import urllib.parse
            print(urllib.parse.quote(data['repositories'][0]["full_name"], safe=""))
            resp.extend(f'<li><a href="{r["html_url"]}">{r["full_name"]}</a> [<a href="/gh-deploy/{inst_id}/deploy:pypi/{urllib.parse.quote(r["full_name"], safe="")}/master">Deploy master</a>] [<a href="/check-repos/{inst_id}/{urllib.parse.quote(r["full_name"], safe="")}/master/HEAD">Check master</a>]</li>' for r in data['repositories'])
            resp.append('</ul>')
        # import ipdb; ipdb.set_trace()
        return resp

    @cherrypy.expose
    @cherrypy.tools.sessions()
    def gh_deploy(self, installation_id, task_tag='deploy:pypi', repo_slug='webknjaz/.me', ref='master'):
        global app_id

        print(f'==============> Requesting deploy of {ref}')

        access_token = cherrypy.session['gh_access_token']
        print(access_token)
	#requests.post('https://github.com/login/oauth/access_token', data=data).text.lstrip('access_token=').rstrip('&token_type=bearer')
        #gh_user = requests.get(f'https://api.github.com/user?access_token={access_token}').json()
        dpl_res = requests.post(f'https://api.github.com/repos/{repo_slug}/deployments?access_token={access_token}', json={'ref': ref, 'task': task_tag})
        return 'OK'
        import ipdb; ipdb.set_trace()
        gh_int = get_github_integration(app_id, private_key_path)
        gh_client = get_installation_client(gh_int, installation_id)

        rp = gh_client.get_repo(repo_slug)
        #import ipdb; ipdb.set_trace()
        post_parameters = {'ref': ref, 'task': task_tag}
        headers, data = rp._requester.requestJsonAndCheck(
            "POST",
            rp.url + "/deployments",
            input=post_parameters
        )
        pprint(headers)
        pprint(data)
        return 'OK'

    @classmethod
    def run_server(cls, cp_config={}, app_config={}):
        global_config = cp_config.copy()
        global_config['server.socket_host'] = global_config.get('server.socket_host', '0.0.0.0')
        global_config['server.socket_port'] = global_config.get('server.socket_port', 8080)
        cherrypy.config.update(global_config)

        root_app = cls()
        root_app.login = GitHubLogin()
        root_app.gh_events = GitHubEventHandler()

        cherrypy.quickstart(root_app, '/', app_config)


def main():
    GitHubApp.run_server(
        cp_config={'server.socket_port': server_port},
        app_config={
            '/':
                {
                    'tools.sessions.on': True,
                    'tools.trailing_slash.on': False,
                    'request.dispatch': GithubEventDispatcher(),
                },
            '/gh_events/':
                {
                    'tools.trailing_slash.on': False,
                },
         },
    )


__name__ == '__main__' and main()
