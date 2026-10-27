# -*- coding: utf-8 -*-
"""Fold finished sweeps into the job pool.

Survivors go in as Pending, marked [UNREAD] until someone reads them with
`ap.py read`. Closed ads go in as Skipped with the rule's reason, so they are
never fetched again.

The provisional priority is NOT a judgement of fit. It says how likely the
candidate can legally take the job:

    no sponsorship needed in this country     Medium (fit decides later)
    needs sponsorship, ad offers a visa       High
    needs sponsorship, ad offers relocation
      or states English as working language   Medium
    needs sponsorship, ad says neither        Low
    UK with the sponsor register: licensed (exact) High, licensed (prefix)
      Medium, not on the register and the ad silent -> closed

Reading the ad overwrites it. A region with close_low_priority closes Low rows
at ingest unless they are Easy Apply (cheap enough to try anyway).
"""
import csv, datetime, glob, io, os, re

from . import config, pool, sweep
from .screen import Screener

DATE_IN_NAME = re.compile(r'(\d{4}-\d{2}-\d{2})')


def _region_of(run_dir):
    name = os.path.basename(run_dir.rstrip('/\\'))
    m = re.match(r'(.+?)-\d{4}-\d{2}-\d{2}', name)
    return m.group(1) if m else ''


def pending_runs():
    return sorted(d for d in glob.glob(os.path.join(config.runs_dir(), '*'))
                  if os.path.isdir(d) and os.path.exists(os.path.join(d, 'survivors.csv'))
                  and not os.path.exists(os.path.join(d, '.ingested')))


def ingest(run_dir, rows, scr, regions):
    region = _region_of(run_dir)
    reg = regions.get(region, {})
    country = reg.get('country', '')
    _, needs = scr.authorization(country)
    m = DATE_IN_NAME.search(os.path.basename(run_dir))
    day = m.group(1) if m else datetime.date.today().isoformat()
    have = set(r['job_url'] for r in rows)
    uk = {}
    p = os.path.join(run_dir, 'uk_sponsors.csv')
    if os.path.exists(p):
        uk = {r['url']: r for r in csv.DictReader(io.open(p, encoding='utf-8'))}
    added = closed = dup = 0

    def base(m, source):
        r = pool.blank()
        r.update(date_found=day, company=m['company'], job_title=m['title'], location=m['location'],
                 source=source, job_url=m['url'], posted_date=m['posted'], country=country, region=region)
        return r

    for m in csv.DictReader(io.open(os.path.join(run_dir, 'survivors.csv'), encoding='utf-8')):
        if m['url'] in have:
            dup += 1
            continue
        src = 'Platsbanken' if 'arbetsformedlingen' in m['url'] else 'LinkedIn'
        r = base(m, src)
        notes = ['[UNREAD]']
        if m.get('easy_apply'):
            notes.append('[EASYAPPLY]')
        if not needs:
            pri = 'Medium'
        elif m['url'] in uk:
            u = uk[m['url']]
            v, conf = u['uk_sponsor'], u['uk_sponsor_confidence']
            pri = 'High' if v == 'licensed' and conf == 'exact' else \
                  'Medium' if v in ('licensed', 'ambiguous') else 'Low'
            notes.append('UK sponsor register: %s%s (%s).' % (
                v, (' as "%s"' % u['uk_sponsor_match']) if u['uk_sponsor_match'] else '', conf))
            if v == 'not on the register':
                if m['sponsor'] == 'silent':
                    r.update(priority='Low', status='Skipped',
                             skip_reason='Employer not found on the UK sponsor register and the ad says nothing '
                                         'about visas (name match; check by hand to re-open)',
                             notes=' '.join(notes[1:]))
                    rows.append(r)
                    have.add(m['url'])
                    closed += 1
                    continue
                pri = 'Medium'
                notes.append('CONTRADICTION: not on the register, but the ad mentions visa or relocation support. Check by hand.')
        else:
            pri = 'High' if m['sponsor'] == 'visa' else \
                  'Medium' if (m['sponsor'] == 'relocation' or m['english'] == 'stated') else 'Low'
        if needs:
            notes.append('Needs sponsorship here. Ad on visas: %s. Ad on English: %s.' % (m['sponsor'], m['english']))
        d = pool.duplicate_of(rows, m['company'], m['title'], m['url'])
        if d:
            r['next_action'] = 'CHECK: same company and title as a %s row (%s, %s); may be the same ad under another id' % (
                d['status'], d['location'], d['date_found'])
        r.update(priority=pri, status='Pending', notes=' '.join(notes))
        if pri == 'Low' and reg.get('close_low_priority') and not m.get('easy_apply'):
            r.update(status='Skipped', skip_reason='Low priority in a region set to close Low rows at ingest')
            closed += 1
        else:
            added += 1
        rows.append(r)
        have.add(m['url'])

    for fname, stage in (('closed_by_title.csv', 'title check'), ('closed_by_body.csv', 'body scan')):
        p = os.path.join(run_dir, fname)
        if not os.path.exists(p):
            continue
        for m in csv.DictReader(io.open(p, encoding='utf-8')):
            if m['url'] in have:
                continue
            r = base(m, 'Platsbanken' if 'arbetsformedlingen' in m['url'] else 'LinkedIn')
            r.update(priority='Low', status='Skipped', skip_reason=m['reason'],
                     notes='Closed by the %s; no human read it.' % stage)
            rows.append(r)
            have.add(m['url'])
            closed += 1
    io.open(os.path.join(run_dir, '.ingested'), 'w').write(datetime.datetime.now().isoformat())
    sweep.unqueue(run_dir)
    print('%-34s pending +%d   skipped +%d   already in pool %d'
          % (os.path.basename(run_dir), added, closed, dup))
    return added


def main(run_dirs=None):
    runs = run_dirs or pending_runs()
    if not runs:
        print('nothing to ingest')
        return
    rows = pool.read()
    scr = Screener(profile=config.profile())
    regions = {r['name']: r for r in config.search().get('regions', [])}
    total = sum(ingest(d, rows, scr, regions) for d in runs)
    pool.write(rows)
    n = pool.rebuild_index(rows)
    print('pending added: %d   pool rows: %d   index keys: %d' % (total, len(rows), n))
    print('next: python pipeline/ap.py read --list')
