# -*- coding: utf-8 -*-
"""One sweep of one region: collect, triage by title, fetch bodies, scan.

    runs/<region>-<date>-<hour>/
        cards/              raw search pages
        jd/                 ad pages (LinkedIn) or wrapped ad text (Platsbanken)
        sweep_log.csv       one line per source x location x keyword
        meta.csv            ads whose title passed; their bodies were fetched
        closed_by_title.csv ads closed on the title alone
        survivors.csv       ads the body scan kept: these need a read
        closed_by_body.csv  ads the body scan closed, with the reason

A sweep never writes to the pool. `ingest` does that, so an unattended run can
never mark an ad as screened that nobody read. The window is gap-aware: a
region whose last successful sweep was 30 hours ago gets a 30-hour window, so a
missed day (laptop asleep, network down) is caught up by the next run.
"""
import csv, datetime, io, os, re, time

from . import config, linkedin, platsbanken, pool, uk_sponsors
from .screen import Screener

COLS = ['jobid', 'company', 'title', 'location', 'posted', 'url']


def _stamp(region):
    return os.path.join(config.runs_dir(), '.last_success_%s' % region)


def window_hours(region, search, override=None):
    w = search.get('window') or {}
    default, mx = int(w.get('default_hours', 24)), int(w.get('max_hours', 168))
    if override:
        return int(override), False
    p = _stamp(region)
    if not os.path.exists(p):
        return default, False
    try:
        prev = int(io.open(p).read().strip())
    except ValueError:
        return default, False
    gap = int((time.time() - prev + 3599) // 3600)
    return max(default, min(gap, mx)), gap > default


def _write(path, rows, cols):
    with io.open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def run(region_name, hours=None, dry=False):
    search = config.search()
    regions = {r['name']: r for r in search.get('regions', [])}
    if region_name not in regions:
        raise SystemExit('unknown region "%s". Regions in search.json: %s'
                         % (region_name, ', '.join(regions) or '(none)'))
    reg = regions[region_name]
    keywords = list(search.get('keywords', [])) + list(reg.get('extra_keywords', []))
    pause = float(search.get('pause_seconds', 1.0))
    hrs, widened = window_hours(region_name, search, hours)
    now = datetime.datetime.now()
    out = os.path.join(config.runs_dir(), '%s-%s' % (region_name, now.strftime('%Y-%m-%d-%H')))
    for d in ('cards', 'jd'):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    print('region %s  window %dh%s  ->  %s' % (region_name, hrs,
          '  (widened to cover the gap since the last run)' if widened else '', out))
    sources = reg.get('sources', ['linkedin'])
    log = []

    # --- collect + title triage ------------------------------------------
    scr = Screener(profile=config.profile())
    seen = pool.seen_keys()
    keep, closed_t = {}, []
    if 'linkedin' in sources:
        win = hrs * 3600
        for loc in reg.get('locations', []):
            print('== %s ==' % loc)
            base, bo = linkedin.fetch_axis(out, loc, linkedin.NONSENSE, win, 'base', pause=pause)
            print('  %-28s %4d cards   noise floor' % ('(nonsense keyword)', base))
            log.append(('linkedin', loc, linkedin.NONSENSE, win, base, 'NOISE_FLOOR_' + bo))
            for kw in ([] if dry else keywords):
                n, o = linkedin.fetch_axis(out, loc, kw, win, 'p', pause=pause)
                # A capped floor says nothing: every keyword looks "at or below" 100.
                flag = (' <- at/below the noise floor: padding, not matches'
                        if base and bo != 'CAP' and n <= base else '')
                print('  %-28s %4d cards   %s%s' % (kw, n, o, flag))
                log.append(('linkedin', loc, kw, win, n, o + flag))
                if o == 'CAP':
                    # The cap keeps the most relevant 100 of the whole window, so
                    # the newer half is fetched again on its own to reach the rest.
                    n2, o2 = linkedin.fetch_axis(out, loc, kw, win // 2, 'f', pause=pause)
                    print('  %-28s %4d cards   %s (newer half of the window)' % ('  ^ recovery', n2, o2))
                    log.append(('linkedin', loc, kw, win // 2, n2, 'RECOVERY_' + o2))
        cards = linkedin.parse_cards(os.path.join(out, 'cards'))
        fresh = {k: v for k, v in cards.items()
                 if pool.key_for(v['url'], v['company'], v['title']) not in seen}
        for k, v in fresh.items():
            if scr.title_ok(v['title']):
                keep[k] = v
            else:
                closed_t.append(dict(v, reason=scr.title_reason(v['title'])))
        print('linkedin: %d cards, %d not seen before, %d passed the title check'
              % (len(cards), len(fresh), len([k for k in keep if not k.startswith('pb')])))
    if 'platsbanken' in sources and not dry:
        found = platsbanken.collect(keywords, hrs * 60, log)
        n0 = len(keep)
        for i, h in found.items():
            r = platsbanken.row_of(h)
            if pool.key_for(r['url']) in seen:
                continue
            if scr.title_ok(r['title']):
                keep[r['jobid']] = r
                platsbanken.write_body(out, h)
            else:
                closed_t.append(dict(r, reason=scr.title_reason(r['title'])))
        print('platsbanken: %d ads, %d new titles passed' % (len(found), len(keep) - n0))
    with io.open(os.path.join(out, 'sweep_log.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['source', 'location', 'keyword', 'window_s', 'count', 'outcome'])
        w.writerows(log)
    _write(os.path.join(out, 'meta.csv'), [keep[k] for k in sorted(keep)], COLS)
    _write(os.path.join(out, 'closed_by_title.csv'), closed_t, COLS + ['reason'])

    # --- fetch bodies -------------------------------------------------------
    li_ids = [k for k in sorted(keep) if not k.startswith('pb')]
    print('fetching %d descriptions...' % len(li_ids))
    for i, k in enumerate(li_ids):
        linkedin.fetch_description(out, k)
        time.sleep(pause)
        if i and i % 50 == 0:
            print('  %d / %d' % (i, len(li_ids)))

    # --- body scan ------------------------------------------------------------
    surv, closed_b = [], []
    for k in sorted(keep):
        m = keep[k]
        p = os.path.join(out, 'jd', k + '.html')
        if not os.path.exists(p) or os.path.getsize(p) < 200:
            closed_b.append(dict(m, reason='Description could not be fetched'))
            continue
        text = linkedin.body_text(p)
        why = scr.verdict(text, m['title'], reg.get('country', ''))
        if why:
            closed_b.append(dict(m, reason=why))
        else:
            surv.append(dict(m, sponsor=scr.sponsor_grade(text),
                             english='stated' if scr.english_stated(text) else 'silent',
                             easy_apply='yes' if linkedin.is_easy_apply(p) else ''))
    _write(os.path.join(out, 'survivors.csv'), surv, COLS + ['sponsor', 'english', 'easy_apply'])
    _write(os.path.join(out, 'closed_by_body.csv'), closed_b, COLS + ['reason'])
    from collections import Counter
    print('\nscanned %d: %d to read, %d closed' % (len(keep), len(surv), len(closed_b)))
    for why, n in Counter(r['reason'] for r in closed_b).most_common():
        print('  %4d  %s' % (n, why))
    if reg.get('uk_sponsor_register'):
        uk_sponsors.annotate(out)

    capped = sum(1 for x in log if x[5] == 'CAP')
    walled = sum(1 for x in log if 'WALL' in x[5])
    _queue(region_name, now, len(surv), hrs, capped, walled, out)
    if not dry and walled == 0:
        io.open(_stamp(region_name), 'w').write(str(int(time.time())))
    elif walled:
        print('\n%d axes were blocked by LinkedIn: the window is NOT marked as covered, '
              'so the next run reaches back over it.' % walled)
    print('\nnext: python pipeline/ap.py ingest')
    return out


def _queue(region, now, n, hrs, capped, walled, out):
    """One line per run in PENDING_REVIEW.md, between markers this code owns."""
    p = config.path('PENDING_REVIEW.md')
    line = '- **%s %s** %d to read, %dh window, capped axes %d, blocked axes %d, `%s`' % (
        now.strftime('%Y-%m-%d %H:00'), region, n, hrs, capped, walled,
        os.path.relpath(out, config.home()).replace('\\', '/'))
    text = io.open(p, encoding='utf-8').read() if os.path.exists(p) else \
        '# Pending review\n\nRuns waiting to be ingested and read. `ap.py ingest` clears a run from this list.\n\n<!-- QUEUE:BEGIN -->\n<!-- QUEUE:END -->\n'
    a, b = text.find('<!-- QUEUE:BEGIN -->'), text.find('<!-- QUEUE:END -->')
    if a < 0 or b < 0:
        text += '\n<!-- QUEUE:BEGIN -->\n<!-- QUEUE:END -->\n'
        a, b = text.find('<!-- QUEUE:BEGIN -->'), text.find('<!-- QUEUE:END -->')
    body = [l for l in text[a:b].split('\n')[1:] if l.strip() and os.path.basename(out) not in l]
    body.append(line)
    text = text[:a] + '<!-- QUEUE:BEGIN -->\n' + '\n'.join(body) + '\n' + text[b:]
    io.open(p, 'w', encoding='utf-8').write(text)


def unqueue(run_dir):
    p = config.path('PENDING_REVIEW.md')
    if not os.path.exists(p):
        return
    name = os.path.basename(run_dir.rstrip('/\\'))
    lines = [l for l in io.open(p, encoding='utf-8').read().split('\n') if not (name in l and l.startswith('- '))]
    io.open(p, 'w', encoding='utf-8').write('\n'.join(lines))
