# -*- coding: utf-8 -*-
"""The job pool (dashboard/job_pool.csv) and the derived seen index.

The pool is the record: one row per ad ever seen, with its status and the
reason for it. Nothing is deleted, so a closed ad is never screened twice.
seen_index.csv is a projection rebuilt from the pool; never edit it by hand.

Statuses: Pending (open, not yet acted on), Needs user (blocked on something
only the candidate can do), Submitted, Skipped (closed, with skip_reason).
"""
import csv, io, os, re

from . import config

FIELDS = ['date_found', 'company', 'job_title', 'role_family', 'level', 'location',
          'remote_policy', 'source', 'job_url', 'posted_date', 'priority', 'status',
          'resume_variant', 'skip_reason', 'blocker', 'next_action', 'notes',
          'country', 'region']
OPEN = ('Pending', 'Needs user')

LI = re.compile(r'linkedin\.com/jobs/view/(\d+)')
PB = re.compile(r'arbetsformedlingen\.se/[^ ]*?/(\d+)')


def read():
    p = config.pool_path()
    if not os.path.exists(p):
        return []
    with io.open(p, encoding='utf-8', errors='replace', newline='') as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in FIELDS:
            r.setdefault(k, '')
            if r[k] is None:
                r[k] = ''
    return rows


def write(rows):
    p = config.pool_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    extra = []
    for r in rows:
        for k in r:
            if k not in FIELDS and k not in extra and not k.startswith('_'):
                extra.append(k)
    tmp = p + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS + extra, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, p)


def norm(s, kind='title'):
    """Company names lose bracketed noise and legal suffixes; titles keep
    brackets (they can carry meaning) but lose gender tags like (m/w/d)."""
    s = (s or '').lower()
    if kind == 'company':
        s = re.sub(r'\(.*?\)', ' ', s)
    s = re.sub(r'\((?:client|kund)[^)]*\)', ' ', s)
    s = re.sub(r'\(\s*[mwfdhx]\s*[/|]\s*[mwfdhx](?:\s*[/|]\s*[mwfdhx])?\s*\)', ' ', s)
    s = re.sub(r'\((all genders|alle geschlechter)\)', ' ', s)
    s = re.sub(r'[^a-z0-9À-ɏ一-鿿]+', ' ', s)
    s = re.sub(r'\b(ab|a s|aps|oy|gmbh|inc|ltd|limited|bv|b v|group)\b', ' ', s)
    return ' '.join(s.split())


def key_for(url, company='', title=''):
    """A stable id for an ad: the board's own id when the URL has one."""
    m = LI.search(url or '')
    if m:
        return 'li:' + m.group(1)
    m = PB.search(url or '')
    if m:
        return 'pb:' + m.group(1)
    return 'nm:' + norm(company, 'company') + '|' + norm(title)


def rebuild_index(rows=None):
    rows = read() if rows is None else rows
    rank = {'Submitted': 4, 'Needs user': 3, 'Pending': 2, 'Skipped': 1}
    seen = {}
    for r in rows:
        k = key_for(r['job_url'], r['company'], r['job_title'])
        rec = [k, r['company'], r['job_title'], r['status'], r['date_found'],
               r['location'], (r['skip_reason'] or '')[:90]]
        if k not in seen or rank.get(rec[3], 0) > rank.get(seen[k][3], 0):
            seen[k] = rec
    out = sorted(seen.values(), key=lambda x: (x[3], x[1].lower()))
    p = config.index_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['key', 'company', 'title', 'status', 'date_screened', 'location', 'why'])
        w.writerows(out)
    return len(out)


def seen_keys():
    p = config.index_path()
    if not os.path.exists(p):
        return set()
    with io.open(p, encoding='utf-8') as f:
        return set(r['key'] for r in csv.DictReader(f))


# --------------------------------------------------------- duplicate check
# LinkedIn lists one ad once per city, each with its own job id, so the same
# role can reach the pool twice. A repeat of a submitted or open row is
# FLAGGED, never closed: an agency can run two real roles under one title.
def _title_key(company, title):
    t = re.sub(r'\(.*?\)', ' ', (title or '').lower())
    t = re.sub(r'[^a-z0-9À-ɏ]+', ' ', t)
    return ((company or '').strip().lower(), ' '.join(t.split()))


def duplicate_of(rows, company, title, url):
    """The earlier Submitted or open row this one repeats, or None."""
    k = _title_key(company, title)
    for r in rows:
        if r['job_url'] != url and r['status'] in ('Submitted',) + OPEN \
                and _title_key(r['company'], r['job_title']) == k:
            return r
    return None


def blank():
    return {k: '' for k in FIELDS}


def set_status(changes, today):
    """changes: list of dicts key,status,reason (key = job id, pb<id> or URL)."""
    rows = read()

    def k_of(url):
        m = LI.search(url or '')
        if m:
            return m.group(1)
        m = PB.search(url or '')
        if m:
            return 'pb' + m.group(1)
        return url
    want = {}
    for c in changes:
        k = c['key'].strip()
        want[k_of(k) if k.startswith('http') else k] = c
    hit = set()
    for r in rows:
        k = k_of(r['job_url'])
        if k not in want or r['status'] == 'Submitted':
            continue
        c = want[k]
        r['status'] = c['status']
        if c['status'] == 'Skipped':
            r['skip_reason'] = c.get('reason', '')
            r['next_action'] = 'None'
        else:
            r['next_action'] = c.get('reason', '')
        r['notes'] = (r['notes'] + ' | ' if r['notes'] else '') + '%s %s: %s' % (
            today, c['status'], c.get('reason', ''))
        hit.add(k)
    write(rows)
    rebuild_index(rows)
    return hit, sorted(set(want) - hit)
