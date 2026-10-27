# -*- coding: utf-8 -*-
"""Check employers against the UK Home Office register of licensed sponsors.

In most countries whether an employer can sponsor a visa is only knowable from
what the ad says, which is usually nothing. The UK is different: an employer
cannot sponsor a Skilled Worker visa without a licence, and the register is
public. Download the CSV from
https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers
to <workspace>/data/uk_sponsor_register.csv (it is republished most working days).

A hit means the organisation COULD sponsor, not that it will sponsor this role.
A miss is the stronger signal. LinkedIn shows trading names and the register
holds legal names, so matching runs in two passes and always reports the
matched register line so it can be checked by eye:

    exact   normalised names are equal                        -> safe
    prefix  one name starts the other at a word boundary,     -> check the name
            and only one register entry matches
"""
import csv, io, os, re

from . import config

SUFFIX = re.compile(r'\b(limited|ltd|llp|llc|plc|inc|incorporated|corp|corporation|company)\b')
PUNCT = re.compile(r'[^a-z0-9 ]+')
GENERIC = {'data', 'technology', 'technologies', 'software', 'digital', 'analytics', 'solutions',
           'consulting', 'partners', 'services', 'systems', 'research', 'health', 'energy',
           'finance', 'capital'}


def reg_path():
    return config.path('data', 'uk_sponsor_register.csv')


def norm(name):
    s = (name or '').lower().replace('&', ' and ')
    s = SUFFIX.sub(' ', PUNCT.sub(' ', s))
    return ' '.join(s.split())


class Register(object):
    def __init__(self, path=None):
        self.exact, self.rows = {}, 0
        path = path or reg_path()
        if not os.path.exists(path):
            return
        for r in csv.DictReader(io.open(path, encoding='utf-8-sig', errors='replace')):
            if (r.get('Route') or '').strip() != 'Skilled Worker':
                continue
            raw = (r.get('Organisation Name') or '').strip()
            n = norm(raw)
            if n:
                self.rows += 1
                self.exact.setdefault(n, (raw, (r.get('Town/City') or '').strip()))
        self.keys = sorted(self.exact)

    def lookup(self, company):
        """-> (verdict, matched_name, confidence)"""
        n = norm(company)
        if not n:
            return 'unknown', '', 'no company name'
        if n in self.exact:
            return 'licensed', self.exact[n][0], 'exact'
        if n in GENERIC or n.split()[0] in GENERIC or len(n) < 4:
            return 'not on the register', '', 'exact only (name too short or generic to prefix-match)'
        hits = [k for k in self.keys if k.startswith(n + ' ')]
        if len(hits) == 1:
            return 'licensed', self.exact[hits[0]][0], 'prefix - CHECK THE MATCHED NAME'
        if hits:
            return 'ambiguous', '%s (+%d more)' % (self.exact[hits[0]][0], len(hits) - 1), 'prefix, not unique'
        return 'not on the register', '', 'no match'


def annotate(outdir):
    reg = Register()
    if not reg.rows:
        print('UK sponsor register missing at %s - skipped (see pipeline/README.md)' % reg_path())
        return
    src = os.path.join(outdir, 'survivors.csv')
    rows = list(csv.DictReader(io.open(src, encoding='utf-8')))
    for r in rows:
        r['uk_sponsor'], r['uk_sponsor_match'], r['uk_sponsor_confidence'] = reg.lookup(r['company'])
    cols = (list(rows[0].keys()) if rows else ['url'])
    with io.open(os.path.join(outdir, 'uk_sponsors.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print('UK sponsor register (%d Skilled Worker entries):' % reg.rows,
          dict(Counter(r['uk_sponsor'] for r in rows)))
