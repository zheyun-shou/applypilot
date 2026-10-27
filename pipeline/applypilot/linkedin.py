# -*- coding: utf-8 -*-
"""LinkedIn's public (logged-out) job search endpoints.

Three facts about these endpoints shape everything below. All three were
measured, and all three fail silently if ignored.

1. NO ZERO RESULTS. A keyword the engine cannot match does not return an empty
   page. It returns a generic job feed. A nonsense keyword ("zzqxwv") is
   therefore searched first in every location to measure that noise floor. An
   axis at or below the floor returned padding, not matches.

2. A HARD CAP OF 100. Pages hold 10 cards and stop at start=90. A full page at
   start=90 means the axis was truncated. That is reported as CAP, never as a
   complete sweep. The fix is a shorter window, which is why sweeps run daily.
   There is no date-range parameter (only "last N seconds"), so a missed day
   can only be recovered by widening the window, where more axes hit the cap.

3. THE WALL. LinkedIn sometimes answers a guest request with a login redirect
   or a javascript challenge instead of cards. Such a page holds no cards, so
   a naive counter reads it as "0 cards, done". A genuinely empty page is about
   26 bytes. Anything else without cards is treated as a block: back off,
   retry, and if it persists log the axis as INCOMPLETE.
"""
import glob, html, io, os, re, time, urllib.parse, urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/128.0 Safari/537.36')
SEARCH = 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search'
POSTING = 'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/%s'
CARD_TITLE = 'base-search-card__title'
NONSENSE = 'zzqxwv'


def job_url(jobid):
    return 'https://www.linkedin.com/jobs/view/%s/' % jobid


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:  # network errors are logged as a wall, then retried
        return 'FETCH_ERROR %s' % e


def _is_answer(text):
    """True for a real answer: cards, or the tiny genuinely-empty page."""
    if CARD_TITLE in text:
        return True
    return len(text) <= 200 and 'authwall' not in text and '/uas/login' not in text \
        and not text.startswith('FETCH_ERROR')


def fetch_axis(outdir, location, keyword, window_s, tag, retries=4, backoff=12, pause=1.0):
    """Page through one keyword in one location. Returns (cards, outcome).

    outcome is EXHAUSTED (a short page ended it), CAP (truncated at 100), or
    WALL_AT_START_n (blocked; the axis is incomplete)."""
    total, outcome = 0, 'EXHAUSTED'
    safe = re.sub(r'[^A-Za-z0-9_]+', '', '%s_%s_%s' % (location, keyword, tag))
    for start in range(0, 100, 10):
        url = SEARCH + '?' + urllib.parse.urlencode({
            'keywords': keyword, 'location': location,
            'f_TPR': 'r%d' % window_s, 'start': start})
        f = os.path.join(outdir, 'cards', '%s_s%d.html' % (safe, start))
        for attempt in range(retries + 1):
            text = _get(url)
            if _is_answer(text):
                break
            if attempt == retries:
                io.open(f, 'w', encoding='utf-8').write(text)
                return total, 'WALL_AT_START_%d' % start
            time.sleep(backoff * (attempt + 1))
        io.open(f, 'w', encoding='utf-8').write(text)
        n = text.count(CARD_TITLE)
        total += n
        time.sleep(pause)
        if n < 10:
            break
        if start == 90:
            outcome = 'CAP'
    return total, outcome


CARD = re.compile(r'<li>(.*?)</li>', re.S)


def parse_cards(cards_dir):
    """Every card in the stored search pages, keyed by LinkedIn job id."""
    rows = {}
    for f in sorted(glob.glob(os.path.join(cards_dir, '*.html'))):
        txt = io.open(f, encoding='utf-8', errors='replace').read()
        for c in CARD.findall(txt):
            m = re.search(r'urn:li:jobPosting:(\d+)', c)
            if not m:
                continue

            def grab(pat):
                g = re.search(pat, c, re.S)
                return html.unescape(re.sub(r'<[^>]+>', '', g.group(1))).strip() if g else ''
            dt = re.search(r'datetime="([\d-]+)"', c)
            rows[m.group(1)] = {
                'jobid': m.group(1),
                'company': grab(r'class="base-search-card__subtitle"[^>]*>(.*?)</h4>'),
                'title': grab(r'class="base-search-card__title"[^>]*>(.*?)</h3>'),
                'location': grab(r'class="job-search-card__location"[^>]*>(.*?)</span>'),
                'posted': dt.group(1) if dt else '',
                'url': job_url(m.group(1)),
            }
    return rows


def fetch_description(outdir, jobid, retries=2):
    """Store the ad page as jd/<jobid>.html. Skips ids already stored."""
    p = os.path.join(outdir, 'jd', '%s.html' % jobid)
    if os.path.exists(p) and os.path.getsize(p) > 200:
        return True
    for attempt in range(retries + 1):
        text = _get(POSTING % jobid, timeout=20)
        if len(text) > 200 and not text.startswith('FETCH_ERROR'):
            io.open(p, 'w', encoding='utf-8').write(text)
            return True
        time.sleep(5 * (attempt + 1))
    return False


def body_text(path):
    """Plain text of a stored ad page, with LinkedIn's sign-in chrome removed."""
    s = io.open(path, encoding='utf-8', errors='replace').read()
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<br\s*/?>|</p>|</li>|</ul>|</h\d>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'[ \t]+', ' ', html.unescape(s))
    lines = [l.strip() for l in s.split('\n') if l.strip()]
    idx = [i for i, l in enumerate(lines) if 'Cookie Policy' in l]
    return '\n'.join(lines[max(idx) + 1:] if idx else lines)


def is_easy_apply(path):
    """The stored guest page shows an on-site apply button for Easy Apply ads."""
    try:
        return 'apply-link-onsite' in io.open(path, encoding='utf-8', errors='replace').read()
    except IOError:
        return False
