#! /usr/bin/env python

from functools import lru_cache, partial
from pprint import pprint
import textwrap
from warnings import catch_warnings

import cherrypy

from envparse import Env
from github import Github, GithubIntegration
import requests


with catch_warnings(record=True):
    Env.read_envfile()

env = Env()

app_id = env('GH_APP_ID', cast=int)
install_id = env('GH_INSTALL_ID', cast=int)
private_key_path = env('GH_PRIVATE_KEY_PATH')

# oauth:
client_id = env('GH_OAUTH_CLIENT_ID')
client_secret = env('GH_OAUTH_CLIENT_SECRET')

ngrok_tun = env('NGROK_TUN_SLUG')
gh_auth_url = f'https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri=https%3A%2F%2F{ngrok_tun}.ngrok.io%2Flogin%2Foauth&state=secret-xxx'

cache_once = partial(lru_cache, maxsize=32)


def dispatch_github_event(next_dispatcher = cherrypy.dispatch.Dispatcher()):
    def dispatch_event(path_info):
        request = cherrypy.serving.request
        header = request.headers.get
        gh_event = header('X-GitHub-Event')
        cherrypy.request.github_event = gh_event
        #import ipdb; ipdb.set_trace()
        print(gh_event)
        return next_dispatcher(path_info)

    return dispatch_event


class GithubEventDispatcher(cherrypy.dispatch.Dispatcher):
    def __call__(self, path_info):
        request = cherrypy.serving.request
        header = request.headers.get
        gh_event, gh_delivery = header('X-GitHub-Event'), header('X-GitHub-Delivery')
        if not gh_event:
            return super().__call__(path_info)
        cherrypy.request.github_event = gh_event
        cherrypy.request.github_delivery = gh_delivery
        new_path_info = '/'.join((path_info.rstrip('/'), gh_event))
        print(gh_event, gh_delivery)
        print(new_path_info)
        return super().__call__(new_path_info)


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
        import ipdb; ipdb.set_trace()
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
    def run_server(cls, cp_config={}):
        root_app = cls()
        root_app.login = GitHubLogin()
        root_app.gh_events = GitHubEventHandler()
        cherrypy.quickstart(root_app, '/', cp_config)



@cherrypy.tools.json_in()
@cherrypy.expose
class GitHubEventHandler:
    @cherrypy.tools.json_in()
    @cherrypy.expose
    def deployment(self):
        """

        Example payload::

        {
          "deployment": {
            "url": "https://api.github.com/repos/webknjaz/.me/deployments/86387934",
            "id": 86387934,
            "sha": "05a00f509f344d92306bd6e73c27eb74e4534b87",
            "ref": "master",
            "task": "deploy",
            "payload": {

            },
            "environment": "production",
            "description": null,
            "creator": {
              "login": "dobby-ans[bot]",
              "id": 37545855,
              "avatar_url": "https://avatars2.githubusercontent.com/u/578543?v=4",
              "gravatar_id": "",
              "url": "https://api.github.com/users/dobby-ans%5Bbot%5D",
              "html_url": "https://github.com/apps/dobby-ans",
              "followers_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/followers",
              "following_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/following{/other_user}",
              "gists_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/gists{/gist_id}",
              "starred_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/starred{/owner}{/repo}",
              "subscriptions_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/subscriptions",
              "organizations_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/orgs",
              "repos_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/repos",
              "events_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/events{/privacy}",
              "received_events_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/received_events",
              "type": "Bot",
              "site_admin": false
            },
            "created_at": "2018-05-20T23:59:21Z",
            "updated_at": "2018-05-20T23:59:21Z",
            "statuses_url": "https://api.github.com/repos/webknjaz/.me/deployments/86387934/statuses",
            "repository_url": "https://api.github.com/repos/webknjaz/.me"
          },
          "repository": {
            "id": 54188009,
            "name": ".me",
            "full_name": "webknjaz/.me",
            "owner": {
              "login": "webknjaz",
              "id": 578543,
              "avatar_url": "https://avatars2.githubusercontent.com/u/578543?v=4",
              "gravatar_id": "",
              "url": "https://api.github.com/users/webknjaz",
              "html_url": "https://github.com/webknjaz",
              "followers_url": "https://api.github.com/users/webknjaz/followers",
              "following_url": "https://api.github.com/users/webknjaz/following{/other_user}",
              "gists_url": "https://api.github.com/users/webknjaz/gists{/gist_id}",
              "starred_url": "https://api.github.com/users/webknjaz/starred{/owner}{/repo}",
              "subscriptions_url": "https://api.github.com/users/webknjaz/subscriptions",
              "organizations_url": "https://api.github.com/users/webknjaz/orgs",
              "repos_url": "https://api.github.com/users/webknjaz/repos",
              "events_url": "https://api.github.com/users/webknjaz/events{/privacy}",
              "received_events_url": "https://api.github.com/users/webknjaz/received_events",
              "type": "User",
              "site_admin": false
            },
            "private": false,
            "html_url": "https://github.com/webknjaz/.me",
            "description": null,
            "fork": false,
            "url": "https://api.github.com/repos/webknjaz/.me",
            "forks_url": "https://api.github.com/repos/webknjaz/.me/forks",
            "keys_url": "https://api.github.com/repos/webknjaz/.me/keys{/key_id}",
            "collaborators_url": "https://api.github.com/repos/webknjaz/.me/collaborators{/collaborator}",
            "teams_url": "https://api.github.com/repos/webknjaz/.me/teams",
            "hooks_url": "https://api.github.com/repos/webknjaz/.me/hooks",
            "issue_events_url": "https://api.github.com/repos/webknjaz/.me/issues/events{/number}",
            "events_url": "https://api.github.com/repos/webknjaz/.me/events",
            "assignees_url": "https://api.github.com/repos/webknjaz/.me/assignees{/user}",
            "branches_url": "https://api.github.com/repos/webknjaz/.me/branches{/branch}",
            "tags_url": "https://api.github.com/repos/webknjaz/.me/tags",
            "blobs_url": "https://api.github.com/repos/webknjaz/.me/git/blobs{/sha}",
            "git_tags_url": "https://api.github.com/repos/webknjaz/.me/git/tags{/sha}",
            "git_refs_url": "https://api.github.com/repos/webknjaz/.me/git/refs{/sha}",
            "trees_url": "https://api.github.com/repos/webknjaz/.me/git/trees{/sha}",
            "statuses_url": "https://api.github.com/repos/webknjaz/.me/statuses/{sha}",
            "languages_url": "https://api.github.com/repos/webknjaz/.me/languages",
            "stargazers_url": "https://api.github.com/repos/webknjaz/.me/stargazers",
            "contributors_url": "https://api.github.com/repos/webknjaz/.me/contributors",
            "subscribers_url": "https://api.github.com/repos/webknjaz/.me/subscribers",
            "subscription_url": "https://api.github.com/repos/webknjaz/.me/subscription",
            "commits_url": "https://api.github.com/repos/webknjaz/.me/commits{/sha}",
            "git_commits_url": "https://api.github.com/repos/webknjaz/.me/git/commits{/sha}",
            "comments_url": "https://api.github.com/repos/webknjaz/.me/comments{/number}",
            "issue_comment_url": "https://api.github.com/repos/webknjaz/.me/issues/comments{/number}",
            "contents_url": "https://api.github.com/repos/webknjaz/.me/contents/{+path}",
            "compare_url": "https://api.github.com/repos/webknjaz/.me/compare/{base}...{head}",
            "merges_url": "https://api.github.com/repos/webknjaz/.me/merges",
            "archive_url": "https://api.github.com/repos/webknjaz/.me/{archive_format}{/ref}",
            "downloads_url": "https://api.github.com/repos/webknjaz/.me/downloads",
            "issues_url": "https://api.github.com/repos/webknjaz/.me/issues{/number}",
            "pulls_url": "https://api.github.com/repos/webknjaz/.me/pulls{/number}",
            "milestones_url": "https://api.github.com/repos/webknjaz/.me/milestones{/number}",
            "notifications_url": "https://api.github.com/repos/webknjaz/.me/notifications{?since,all,participating}",
            "labels_url": "https://api.github.com/repos/webknjaz/.me/labels{/name}",
            "releases_url": "https://api.github.com/repos/webknjaz/.me/releases{/id}",
            "deployments_url": "https://api.github.com/repos/webknjaz/.me/deployments",
            "created_at": "2016-03-18T09:01:03Z",
            "updated_at": "2017-08-24T07:50:02Z",
            "pushed_at": "2018-04-24T23:44:13Z",
            "git_url": "git://github.com/webknjaz/.me.git",
            "ssh_url": "git@github.com:webknjaz/.me.git",
            "clone_url": "https://github.com/webknjaz/.me.git",
            "svn_url": "https://github.com/webknjaz/.me",
            "homepage": "http://webknjaz.me",
            "size": 25,
            "stargazers_count": 0,
            "watchers_count": 0,
            "language": null,
            "has_issues": true,
            "has_projects": true,
            "has_downloads": true,
            "has_wiki": true,
            "has_pages": true,
            "forks_count": 0,
            "mirror_url": null,
            "archived": false,
            "open_issues_count": 0,
            "license": null,
            "forks": 0,
            "open_issues": 0,
            "watchers": 0,
            "default_branch": "master"
          },
          "sender": {
            "login": "dobby-ans[bot]",
            "id": 37545855,
            "avatar_url": "https://avatars2.githubusercontent.com/u/578543?v=4",
            "gravatar_id": "",
            "url": "https://api.github.com/users/dobby-ans%5Bbot%5D",
            "html_url": "https://github.com/apps/dobby-ans",
            "followers_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/followers",
            "following_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/following{/other_user}",
            "gists_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/subscriptions",
            "organizations_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/orgs",
            "repos_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/repos",
            "events_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/events{/privacy}",
            "received_events_url": "https://api.github.com/users/dobby-ans%5Bbot%5D/received_events",
            "type": "Bot",
            "site_admin": false
          },
          "installation": {
            "id": 114158
          }
        }

        """
        # Note: Sender could be a user or a bot, both have access to this API
        global app_id
        req = cherrypy.request
        headers, gh_event = req.headers, req.json
        inst_id = gh_event['installation']['id']
        dpl_event = gh_event['deployment']
        log_info = textwrap.dedent(f'''
        ==============> Got deployment event
        Installation ID: {inst_id}. App ID: {app_id}.
        --------------> Deploy task: {dpl_event["task"]}
        Requested to deploy: {gh_event["repository"]["full_name"]}@{dpl_event["ref"]}.
        By: {gh_event["sender"]["login"]}
        ''')
        print(log_info)
        gh_int = get_github_integration(app_id, private_key_path)
        gh_client = get_installation_client(gh_int, inst_id)
        # print(gh_client)
        # rp = gh_client.get_repo('webknjaz/.me')
        # print(rp.full_name)
        return log_info
        import ipdb; ipdb.set_trace()

    def installation_repositories(self):
        print(f'Action: {cherrypy.request.json["action"]}')

    def integration_installation_repositories(self):
        print(f'Action: {cherrypy.request.json["action"]}')


    @cherrypy.tools.json_in()
    @cherrypy.expose
    def ping(self):
        """

        Example payload::

        {
          "zen": "Mind your words, they are important.",
          "hook_id": 24283197,
          "hook": {
            "type": "App",
            "id": 24283197,
            "name": "web",
            "active": true,
            "events": [

            ],
            "config": {
              "content_type": "json",
              "insecure_ssl": "0",
              "url": "https://github.com/webknjaz"
            },
            "updated_at": "2018-03-19T14:32:42Z",
            "created_at": "2018-03-19T14:32:42Z",
            "app_id": 10194
          }
        }
        """

        print(f'App ID: {cherrypy.request.json["hook"]["app_id"]}')
        print(f'Zen: {cherrypy.request.json["zen"]}')
        raise cherrypy.HTTPError(204, cherrypy.request.json["zen"])

    @cherrypy.tools.json_in()
    @cherrypy.expose
    def check_run(self):
        raise cherrypy.HTTPError(405, 'Sorry, our GitHub app does not process such event types.')

    @cherrypy.tools.json_in()
    @cherrypy.expose
    def check_suite(self):
        raise cherrypy.HTTPError(405, 'Sorry, our GitHub app does not process such event types.')


class GitHubLogin:
    @cherrypy.expose
    @cherrypy.tools.sessions()
    def index(self):
        try:
            cherrypy.session['gh_access_token']
            raise cherrypy.HTTPRedirect('/list-repos')
        except KeyError:
            raise cherrypy.HTTPRedirect(gh_auth_url)

    @cherrypy.expose
    @cherrypy.tools.sessions()
    def oauth(self, code, state):
        global client_id
        global client_secret
        print(code, state)
        data = {'client_id': client_id, 'client_secret': client_secret, 'code': code}
        access_token = requests.post('https://github.com/login/oauth/access_token', data=data).text.lstrip('access_token=').rstrip('&token_type=bearer')
        print(access_token)
        gh_user = requests.get(f'https://api.github.com/user?access_token={access_token}').json()
        pprint(gh_user)
        pprint(requests.get(f'https://api.github.com/user?access_token={access_token}').json())
        pprint(requests.get(f'https://api.github.com/apps?access_token={access_token}').json())
        user_installations_obj = requests.get(f'https://api.github.com/user/installations?access_token={access_token}', headers={'Accept': 'application/vnd.github.machine-man-preview+json'}).json()
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
        return f'Hi {cherrypy.session["gh_login"]},<br>You have enabled {len(installations)} installations<br><a href="https://github.com/apps/dobby-ans/installations/new">Installs some more</a><br><a href="/list-repos">List repos</a>.'


@cache_once()
def get_app_key(key_path):
    with open(key_path) as f:
        return f.read()


@cache_once()
def get_github_integration(app_id, key_path):
    private_key = get_app_key(key_path)
    return GithubIntegration(app_id, private_key)


#@cache_once()
def get_installation_auth_token(gh_integration, install_id):
    return gh_integration.get_access_token(install_id).token


#@cache_once()
def get_installation_client(gh_integration, install_id):
    return Github(get_installation_auth_token(gh_integration, install_id))


__name__ == '__main__' and GitHubApp.run_server(
    {'/': {'tools.sessions.on': True, 'tools.trailing_slash.on': False, 'request.dispatch': GithubEventDispatcher(), },
     '/gh_events/': {'tools.trailing_slash.on': False}}
)
