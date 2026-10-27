# -*- coding: utf-8 -*-
"""Workspace and configuration loading.

All personal data lives in a WORKSPACE directory, never in the repository:

    <workspace>/
        config/profile.json      facts about the candidate (forms read this)
        config/search.json       what to search and where
        config/screening.json    which ads to close automatically
        dashboard/job_pool.csv   the record of every ad seen
        dashboard/seen_index.csv derived lookup, rebuilt from the pool
        runs/<run>/              one directory per sweep
        PENDING_REVIEW.md        queue of runs waiting for a human read

The workspace is found in this order: --home on the command line, the
APPLYPILOT_HOME environment variable, then <repo>/workspace.
"""
import io, json, os, sys

PIPELINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(PIPELINE)
EXAMPLES = os.path.join(PIPELINE, 'config')

_home = None


def set_home(path):
    global _home
    _home = os.path.abspath(path)


def home():
    if _home:
        return _home
    env = os.environ.get('APPLYPILOT_HOME')
    if env:
        return os.path.abspath(env)
    return os.path.join(REPO, 'workspace')


def path(*parts):
    return os.path.join(home(), *parts)


def pool_path():
    return path('dashboard', 'job_pool.csv')


def index_path():
    return path('dashboard', 'seen_index.csv')


def runs_dir():
    return path('runs')


def _strip_comments(obj):
    """Drop every key that starts with '_' (used for comments in the JSON files)."""
    if isinstance(obj, dict):
        return {k: _strip_comments(v) for k, v in obj.items() if not k.startswith('_')}
    if isinstance(obj, list):
        return [_strip_comments(v) for v in obj]
    return obj


def load_json(name, required=True):
    p = path('config', name)
    if not os.path.exists(p):
        if required:
            raise SystemExit('missing %s - run "python pipeline/ap.py init" first, then edit it' % p)
        return {}
    try:
        with io.open(p, encoding='utf-8-sig') as f:
            return _strip_comments(json.load(f))
    except ValueError as e:
        raise SystemExit('could not parse %s: %s' % (p, e))


def profile():
    return load_json('profile.json')


def search():
    return load_json('search.json')


def screening():
    return load_json('screening.json', required=False)


def utf8_stdout():
    """Print UTF-8 on every console, without wrapping stdout twice."""
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass
