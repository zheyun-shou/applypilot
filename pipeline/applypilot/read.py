# -*- coding: utf-8 -*-
"""The reading pass: what a fit decision turns on, in batches.

    ap.py read --list                      how many [UNREAD] rows, by region
    ap.py read --batch 1 [--region uk]     30 compact digests
    ap.py read --show <jobid>              full text of one ad
    ap.py read --apply verdicts.csv        write the decisions back

verdicts.csv has the columns url,priority,note. priority is High, Medium, Low
or skip. skip closes the row with the note as its skip_reason; the others keep
it Pending with the new priority. Either way the row loses [UNREAD].

Rows are sorted by employer, then title: agencies post ten near-identical ads,
and judging them side by side is faster and more consistent.
"""
import csv, datetime, glob, io, os, re

from . import config, pool
from .linkedin import body_text

BATCH = 30
REQ = re.compile(r'(requir|qualifi|you have|you.ll have|you are|we.re looking|looking for|must |should |'
                 r'experience|expect|skills|profile|degree|background|ideal|essential|desirable|'
                 r'krav|erfarenhet|meriterande|anforderung|profil)', re.I)
YEARS_ANY = re.compile(r'\d+\s*\+?\s*(?:-\s*\d+\s*)?(?:or |eller )?(?:more )?(?:years|yrs|år|jahre)', re.I)
TAG = re.compile(r'Seniority level\s*(.{0,30}?)\s*Employment type\s*(.{0,30}?)\s*(?:Job function|Industries)', re.S)


def _jd_index():
    out = {}
    for d in sorted(glob.glob(os.path.join(config.runs_dir(), '*', 'jd'))):
        for f in os.listdir(d):
            out[os.path.splitext(f)[0]] = os.path.join(d, f)
    return out


def _jobid(url):
    m = re.search(r'/jobs/view/(\d+)', url) or re.search(r'platsbanken/annonser/(\d+)', url)
    if not m:
        return ''
    return ('pb' if 'platsbanken' in url else '') + m.group(1)


def unread(region=None):
    rows = [r for r in pool.read() if r['status'] == 'Pending' and '[UNREAD]' in r['notes']]
    if region:
        rows = [r for r in rows if r['region'] == region]
    rows.sort(key=lambda r: (r['company'].lower(), r['job_title'].lower()))
    return rows


def digest(r, jd, n):
    p = jd.get(_jobid(r['job_url']), '')
    text = body_text(p) if p else ''
    lines = [l.strip() for l in text.split('\n') if 25 < len(l.strip()) < 300]
    req = [l for l in lines if REQ.search(l)][:9] or lines[:6]
    tag = TAG.search(text)
    print('-' * 76)
    print('[%d] %s | %s' % (n, r['company'], r['job_title']))
    print('    %s | %s | posted %s | now %s%s' % (r['region'], r['location'], r['posted_date'], r['priority'],
          ' | EASY APPLY' if '[EASYAPPLY]' in r['notes'] else ''))
    if tag:
        print('    LinkedIn says: %s, %s' % (tag.group(1).strip(), tag.group(2).strip()))
    extra = r['notes'].replace('[UNREAD]', '').replace('[EASYAPPLY]', '').strip()
    if extra:
        print('    %s' % extra[:300])
    if r['next_action']:
        print('    !! %s' % r['next_action'])
    print('    years in text: %s' % (', '.join(sorted(set(YEARS_ANY.findall(text)))) or 'none'))
    print('    %s' % r['job_url'])
    for l in req:
        print('      . %s' % l[:170])
    if not text:
        print('      (no stored description)')


def apply(path):
    v = list(csv.DictReader(io.open(path, encoding='utf-8-sig')))
    rows = pool.read()
    by = {}
    for r in rows:
        if r['status'] == 'Pending':
            by.setdefault(r['job_url'], []).append(r)
    today = datetime.date.today().isoformat()
    done = skipped = 0
    for x in v:
        hits = by.get(x['url'].strip(), [])
        if len(hits) != 1:
            print('  PROBLEM %s: %d pending rows match' % (x['url'], len(hits)))
            continue
        r = hits[0]
        pri, note = x['priority'].strip(), (x.get('note') or '').strip()
        r['notes'] = r['notes'].replace('[UNREAD]', '').strip()
        if pri.lower() == 'skip':
            r.update(status='Skipped', priority='Low', skip_reason=note, next_action='None')
            r['notes'] += ' | READ %s and closed.' % today
            skipped += 1
        elif pri in ('High', 'Medium', 'Low'):
            r['priority'] = pri
            r['notes'] += ' | READ %s: %s. %s' % (today, pri, note)
            done += 1
        else:
            print('  PROBLEM %s: priority must be High, Medium, Low or skip' % x['url'])
    pool.write(rows)
    pool.rebuild_index(rows)
    print('ranked %d   closed %d' % (done, skipped))


def main(args):
    if args.apply:
        return apply(args.apply)
    if args.show:
        p = _jd_index().get(args.show)
        if not p:
            raise SystemExit('no stored description for %s' % args.show)
        print(body_text(p))
        return
    rows = unread(args.region)
    if not args.batch:
        from collections import Counter
        print('unread pending rows: %d (%d batches of %d)' % (len(rows), (len(rows) + BATCH - 1) // BATCH, BATCH))
        for k, n in Counter(r['region'] or '?' for r in rows).most_common():
            print('  %-16s %d' % (k, n))
        return
    i = args.batch - 1
    chunk = rows[i * BATCH:(i + 1) * BATCH]
    print('batch %d of %d (%d ads)' % (args.batch, (len(rows) + BATCH - 1) // BATCH, len(chunk)))
    jd = _jd_index()
    for n, r in enumerate(chunk, i * BATCH + 1):
        digest(r, jd, n)
    print('-' * 76)
    print('Write verdicts as url,priority,note (priority: High, Medium, Low or skip), then:')
    print('  python pipeline/ap.py read --apply verdicts.csv')
