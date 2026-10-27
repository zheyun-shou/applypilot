# -*- coding: utf-8 -*-
"""Platsbanken (Arbetsförmedlingen, Sweden) via the open JobTech search API.

Use it as a second source for Swedish regions. Some employers post only here.
Two things it does better than LinkedIn: total.value is an exact count, so
there is no cap to infer, and the ad text arrives in the same JSON, so there is
no second fetch per ad. Free-text matching is just as loose, so the body scan
still runs on everything it returns.

TLS note: on Windows, Git Bash's curl may reject this host's certificate chain
because its CA bundle lacks the root. Python reads the Windows root store and
validates it fine. Never disable verification to work around it.
"""
import io, json, os, urllib.parse, urllib.request

API = 'https://jobsearch.api.jobtechdev.se'
PAGE = 100
HARD_CAP = 400


def _get(path, **params):
    url = API + path + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def ad_url(jid):
    return 'https://arbetsformedlingen.se/platsbanken/annonser/%s' % jid


def collect(keywords, window_min, log):
    """{id: hit} for every ad any keyword returned inside the window."""
    found = {}
    for kw in keywords:
        try:
            first = _get('/search', q=kw, limit=PAGE, offset=0, **{'published-after': window_min})
        except Exception as e:
            log.append(('platsbanken', '', kw, window_min * 60, 0, 'ERROR %s' % type(e).__name__))
            print('  platsbanken %-24s FAILED %s' % (kw, e))
            continue
        total = (first.get('total') or {}).get('value', 0)
        hits = list(first.get('hits') or [])
        off = PAGE
        while off < min(total, HARD_CAP):
            try:
                hits.extend(_get('/search', q=kw, limit=PAGE, offset=off,
                                 **{'published-after': window_min}).get('hits') or [])
            except Exception:
                break
            off += PAGE
        outcome = 'EXACT' if total <= HARD_CAP else 'CAPPED_AT_%d_OF_%d' % (HARD_CAP, total)
        print('  platsbanken %-24s %4d total  %s' % (kw, total, outcome))
        log.append(('platsbanken', '', kw, window_min * 60, total, outcome))
        for h in hits:
            if h.get('id'):
                found[str(h['id'])] = h
    return found


def row_of(h):
    emp = (h.get('employer') or {}).get('name') or '?'
    addr = h.get('workplace_address') or {}
    loc = ', '.join(x for x in (addr.get('municipality'), addr.get('region')) if x) or 'Sweden'
    return dict(jobid='pb' + str(h['id']), company=emp, title=h.get('headline') or '?',
                location=loc, posted=(h.get('publication_date') or '')[:10], url=ad_url(h['id']))


def write_body(outdir, h):
    """Wrap the ad text as HTML so linkedin.body_text() reads it unchanged."""
    text = (h.get('description') or {}).get('text') or ''
    p = os.path.join(outdir, 'jd', 'pb%s.html' % h['id'])
    with io.open(p, 'w', encoding='utf-8') as f:
        f.write('<html><body><p>' + text.replace('&', '&amp;').replace('<', '&lt;')
                .replace('\n', '<br>') + '</p></body></html>')
