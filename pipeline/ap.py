# -*- coding: utf-8 -*-
"""ApplyPilot pipeline command line. Run `python pipeline/ap.py -h`.

    init                    create the workspace from the examples
    doctor                  check Python, Node, Chrome and the config files
    sweep --region NAME     collect and screen one region (never writes the pool)
    ingest                  fold finished sweeps into the pool
    read ...                the reading pass over [UNREAD] rows
    set changes.csv         set status by job id or URL (key,status,reason)
    board build|sync        the apply board
    status                  pool counts and the review queue
    uk-check NAME...        look employers up in the UK sponsor register
"""
import argparse, csv, datetime, io, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from applypilot import config  # noqa: E402

config.utf8_stdout()


def cmd_init(a):
    h = config.home()
    for d in ('config', 'dashboard', 'runs', 'data'):
        os.makedirs(os.path.join(h, d), exist_ok=True)
    for name in ('profile', 'search', 'screening'):
        dst = os.path.join(h, 'config', name + '.json')
        if os.path.exists(dst):
            print('kept     %s' % dst)
        else:
            shutil.copy(os.path.join(config.EXAMPLES, name + '.example.json'), dst)
            print('created  %s' % dst)
    from applypilot import pool
    if not os.path.exists(config.pool_path()):
        pool.write([])
        print('created  %s' % config.pool_path())
    pool.rebuild_index()
    print('\nworkspace: %s\nNext: edit config/profile.json and config/search.json, then run doctor.' % h)


def cmd_doctor(a):
    ok = True

    def say(good, msg):
        nonlocal ok
        ok = ok and good
        print(('  ok    ' if good else '  FIX   ') + msg)
    print('workspace: %s' % config.home())
    say(sys.version_info >= (3, 8), 'Python %s (3.8+ needed)' % sys.version.split()[0])
    for name in ('profile.json', 'search.json', 'screening.json'):
        p = config.path('config', name)
        if not os.path.exists(p):
            say(False, '%s missing (run init)' % name)
            continue
        try:
            config.load_json(name)
            say(True, '%s parses' % name)
        except SystemExit as e:
            say(False, str(e))
    try:
        prof = config.profile()
        say(prof.get('candidate', {}).get('email', '').endswith('example.com') is False,
            'profile.json has your own details (not the example)')
        cv = (prof.get('automation') or {}).get('resume_file', '')
        say(os.path.exists(cv), 'resume_file exists: %s (only needed for applying)' % cv)
        regions = [r['name'] for r in config.search().get('regions', [])]
        say(bool(regions), 'regions: %s' % ', '.join(regions))
        from applypilot.screen import Screener
        Screener(profile=prof)
        say(True, 'screening rules compile')
    except SystemExit as e:
        say(False, str(e))
    node = shutil.which('node')
    say(bool(node), 'Node.js found (only needed for the apply runners)')
    mods = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apply', 'node_modules', 'playwright-core')
    say(os.path.isdir(mods), 'playwright-core installed (cd pipeline/apply && npm install)')
    from applypilot import uk_sponsors
    print('  info  UK sponsor register: %s' % ('present' if os.path.exists(uk_sponsors.reg_path())
                                              else 'absent (only needed for regions with uk_sponsor_register)'))
    print('\n' + ('all good' if ok else 'fix the lines marked FIX'))


def cmd_sweep(a):
    from applypilot import sweep
    names = [r['name'] for r in config.search().get('regions', [])] if a.region == 'all' else [a.region]
    for n in names:
        sweep.run(n, hours=a.hours)


def cmd_ingest(a):
    from applypilot import ingest
    ingest.main(a.runs or None)


def cmd_read(a):
    from applypilot import read
    read.main(a)


def cmd_set(a):
    from applypilot import pool
    ch = list(csv.DictReader(io.open(a.file, encoding='utf-8-sig')))
    hit, miss = pool.set_status(ch, datetime.date.today().isoformat())
    print('updated %d of %d' % (len(hit), len(ch)))
    if miss:
        print('not found or already Submitted: %s' % ', '.join(miss))


def cmd_board(a):
    from applypilot import board
    if a.action == 'build':
        board.build(a.live)
    else:
        if not a.live:
            raise SystemExit('board sync needs the saved page: ap.py board sync <saved.html>')
        board.sync(a.live)


def cmd_status(a):
    from applypilot import pool
    from collections import Counter
    rows = pool.read()
    print('pool: %d rows' % len(rows))
    for k, n in Counter(r['status'] for r in rows).most_common():
        print('  %-11s %d' % (k, n))
    print('  unread     %d' % sum(1 for r in rows if r['status'] == 'Pending' and '[UNREAD]' in r['notes']))
    p = config.path('PENDING_REVIEW.md')
    if os.path.exists(p):
        q = [l for l in io.open(p, encoding='utf-8').read().split('\n') if l.startswith('- **')]
        print('runs not ingested: %d' % len(q))
        for l in q[-10:]:
            print('  ' + l)


def cmd_uk(a):
    from applypilot import uk_sponsors
    reg = uk_sponsors.Register()
    print('register entries: %d' % reg.rows)
    for n in a.names:
        print('  %-30s %s' % (n, ' | '.join(reg.lookup(n))))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--home', help='workspace directory (default: $APPLYPILOT_HOME or <repo>/workspace)')
    s = p.add_subparsers(dest='cmd')
    s.add_parser('init').set_defaults(f=cmd_init)
    s.add_parser('doctor').set_defaults(f=cmd_doctor)
    x = s.add_parser('sweep')
    x.add_argument('--region', required=True, help='a region name from search.json, or "all"')
    x.add_argument('--hours', type=int, help='force the window instead of the gap-aware default')
    x.set_defaults(f=cmd_sweep)
    x = s.add_parser('ingest')
    x.add_argument('runs', nargs='*', help='run directories (default: every finished, uningested run)')
    x.set_defaults(f=cmd_ingest)
    x = s.add_parser('read')
    x.add_argument('--list', action='store_true')
    x.add_argument('--batch', type=int)
    x.add_argument('--region')
    x.add_argument('--show')
    x.add_argument('--apply')
    x.set_defaults(f=cmd_read)
    x = s.add_parser('set')
    x.add_argument('file', help='CSV with columns key,status,reason')
    x.set_defaults(f=cmd_set)
    x = s.add_parser('board')
    x.add_argument('action', choices=['build', 'sync'])
    x.add_argument('live', nargs='?', help='a saved copy of the live board page')
    x.add_argument('--live', dest='live_opt')
    x.set_defaults(f=cmd_board)
    s.add_parser('status').set_defaults(f=cmd_status)
    x = s.add_parser('uk-check')
    x.add_argument('names', nargs='+')
    x.set_defaults(f=cmd_uk)
    a = p.parse_args()
    if a.home:
        config.set_home(a.home)
    if not getattr(a, 'f', None):
        p.print_help()
        return
    if a.cmd == 'board' and getattr(a, 'live_opt', None):
        a.live = a.live_opt
    a.f(a)


if __name__ == '__main__':
    main()
