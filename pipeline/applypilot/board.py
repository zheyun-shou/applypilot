# -*- coding: utf-8 -*-
"""The apply board: one HTML page listing every open job, with a tick box
(applied) and a remove button (not a fit, with an optional reason).

The page carries its own state in <script id="data">. Published as a claude.ai
artifact with the `artifact` capability, its Save button republishes the page
with the ticks in it, so reading the artifact later returns them. Opened as a
local file, Save downloads the page instead.

    ap.py board build [--live saved.html]   pool -> dashboard/apply_board.html
    ap.py board sync saved.html             ticks -> Submitted, removals -> Skipped

Order of a round: fetch the live page, `sync` it, then `build --live` it, then
republish. Building without --live starts every tick from empty.
"""
import datetime, io, json, os, re

from . import config, pool

TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'board_template.html')
PRI = {'High': 0, 'Medium': 1, 'Low': 2, '': 3}
DEADLINE = re.compile(r'DEADLINE[^0-9]{0,25}(20\d\d-\d\d-\d\d)')
SUBMITTED_ON = re.compile(r'SUBMITTED (20\d\d-\d\d-\d\d)')
STATE = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)


def out_path():
    return config.path('dashboard', 'apply_board.html')


def _state(path):
    m = STATE.search(io.open(path, encoding='utf-8', errors='replace').read())
    if not m:
        raise SystemExit('no board state found in %s' % path)
    return json.loads(m.group(1).replace('\\u003c', '<'))


def _role(i, r):
    todo = r['next_action'] if re.match(r'(YOU|CHECK)\b', r['next_action'] or '') else ''
    dl = DEADLINE.search(' '.join([r['notes'], r['next_action']]))
    sub = SUBMITTED_ON.search(r['notes'])
    why = ''
    if '[UNREAD]' in r['notes']:
        why = 'not read yet'
    else:
        m = re.search(r'READ \d{4}-\d\d-\d\d: \w+\. ([^|]{0,140})', r['notes'])
        why = m.group(1).strip() if m else ''
    return dict(id='r%d' % i, co=r['company'], ti=r['job_title'], url=r['job_url'],
                loc=r['location'], pri=r['priority'] if r['status'] != 'Submitted' else '',
                dl=dl.group(1) if dl else '', sub=(sub.group(1) if sub else '') if r['status'] == 'Submitted' else '',
                via=r['source'] if r['status'] != 'Submitted' else '', why=why, todo=todo)


def build(live=None):
    rows = pool.read()
    keep = [r for r in rows if r['status'] in pool.OPEN + ('Submitted',)]
    roles = [_role(i, r) for i, r in enumerate(keep)]
    idx = {k: [] for k in ('dl', 'needs', 'easy', 'High', 'Medium', 'Low', 'sub')}
    for i, r in enumerate(keep):
        if r['status'] == 'Submitted':
            idx['sub'].append(i)
        elif r['status'] == 'Needs user':
            idx['needs'].append(i)
        elif roles[i]['dl']:
            idx['dl'].append(i)
        elif '[EASYAPPLY]' in r['notes']:
            idx['easy'].append(i)
        else:
            idx[r['priority'] if r['priority'] in PRI and r['priority'] else 'Low'].append(i)
    newest = lambda i: tuple(-int(x) for x in (keep[i]['date_found'] or '0-0-0').split('-') if x.isdigit())
    for k in ('High', 'Medium', 'Low', 'easy', 'needs'):
        idx[k].sort(key=lambda i: (PRI.get(keep[i]['priority'], 3), newest(i), keep[i]['company'].lower()))
    idx['dl'].sort(key=lambda i: roles[i]['dl'])
    idx['sub'].sort(key=lambda i: (roles[i]['sub'] or keep[i]['date_found']), reverse=True)
    sections = [
        dict(eyebrow='01 · Deadlines', title='Closing soon', ids=idx['dl'], fold=False),
        dict(eyebrow='02 · Needs you', title='Blocked on something only you can do', ids=idx['needs'], fold=False),
        dict(eyebrow='03 · LinkedIn Easy Apply', title='A few clicks each', ids=idx['easy'], fold=True),
        dict(eyebrow='04 · High', title='Strong match', ids=idx['High'], fold=False),
        dict(eyebrow='05 · Medium', title='Worth a try', ids=idx['Medium'], fold=True),
        dict(eyebrow='06 · Low', title='If there is time', ids=idx['Low'], fold=True),
        dict(eyebrow='07 · Record', title='Applied', ids=idx['sub'], fold=True),
    ]
    D = dict(title='Apply board',
             lede='Tick a job when you have applied. Remove one that is not a fit; a reason helps. '
                  'Ticked jobs move to the record on the next build.',
             card='', note='', roles=roles, done={}, removed={}, rwhy={}, sections=sections,
             foot='Built %s from %d pool rows · %d open · %d applied' % (
                 datetime.date.today().isoformat(), len(rows), len(keep) - len(idx['sub']), len(idx['sub'])))
    for i in idx['sub']:
        D['done'][roles[i]['id']] = 1
    if live:
        L = _state(live)
        mkey = lambda r: (r['co'], r['ti'], r.get('url', ''))
        old = {r['id']: mkey(r) for r in L.get('roles', [])}
        now = {mkey(r): r['id'] for r in roles}
        carried = 0
        for k in ('done', 'removed'):
            for oid in (L.get(k) or {}):
                nid = now.get(old.get(oid))
                if nid:
                    D[k][nid] = 1
                    carried += 1
                    if k == 'removed' and (L.get('rwhy') or {}).get(oid):
                        D['rwhy'][nid] = L['rwhy'][oid]
        D['note'] = L.get('note', '')
        print('carried %d ticks/removals and the note from %s' % (carried, live))
    tpl = io.open(TPL, encoding='utf-8').read()
    html = tpl.replace('{{DATA}}', json.dumps(D, ensure_ascii=False).replace('<', '\\u003c'))
    p = out_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, 'w', encoding='utf-8').write(html)
    print('wrote %s  (%d open, %d applied)' % (p, len(keep) - len(idx['sub']), len(idx['sub'])))
    print('sections: ' + ', '.join('%s %d' % (s['eyebrow'].split(' · ')[1], len(s['ids'])) for s in sections))


def sync(live):
    """Write the page's ticks and removals into the pool. Matches on URL."""
    L = _state(live)
    by_id = {r['id']: r for r in L.get('roles', [])}
    rows = pool.read()
    by_url = {}
    for r in rows:
        by_url.setdefault(r['job_url'], []).append(r)
    today = datetime.date.today().isoformat()
    ticked = removed = 0
    problems = []

    def find(b):
        hits = [x for x in by_url.get(b['url'], []) if x['status'] != 'Skipped'] or by_url.get(b['url'], [])
        return hits[0] if len(hits) == 1 else None
    for rid in (L.get('done') or {}):
        b = by_id.get(rid)
        x = find(b) if b else None
        if not x:
            problems.append('tick: %s / %s not matched' % (b and b['co'], b and b['ti']))
            continue
        if x['status'] in pool.OPEN:
            x['status'], x['next_action'], x['blocker'] = 'Submitted', 'Await response', ''
            x['notes'] = (x['notes'] + ' | ' if x['notes'] else '') + 'SUBMITTED %s (ticked on the board)' % today
            ticked += 1
    for rid in (L.get('removed') or {}):
        b = by_id.get(rid)
        x = find(b) if b else None
        if not x or x['status'] not in pool.OPEN:
            continue
        why = ((L.get('rwhy') or {}).get(rid) or '').strip()
        x.update(status='Skipped', priority='Low', next_action='None',
                 skip_reason='Removed on the board %s%s' % (today, (': "%s"' % why) if why else ''))
        removed += 1
    pool.write(rows)
    pool.rebuild_index(rows)
    print('ticked -> Submitted: %d   removed -> Skipped: %d' % (ticked, removed))
    for p in problems:
        print('  ' + p)
    if (L.get('note') or '').strip():
        print('\nNOTE ON THE BOARD:\n' + L['note'].strip())
