#! /usr/bin/env python

from functools import lru_cache, partial

from github import Github, GithubIntegration

from .config import (
    app_id,
    install_id,
)


cache_once = partial(lru_cache, maxsize=1)


@cache_once()
def get_app_key(key_path):
    try:
        with open(key_path) as f:
            return f.read()
    except (TypeError, ValueError):
        return env('GH_PRIVATE_KEY')


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
