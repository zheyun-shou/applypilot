# ApplyPilot pipeline

The ApplyPilot skill (the rest of this repository) tells an agent how to run a job search. This folder is the machinery that does the repetitive part:

1. **Sweep.** Collect new ads from LinkedIn's public job search, plus Platsbanken for Sweden, once or twice a day.
2. **Screen.** Close ads by rule: a language you do not work in, a refusal to sponsor where you need sponsorship, a clearance demand, a years bar above your level, gig work. Every closure is recorded with its reason.
3. **Read.** You or your agent read the survivors in compact batches and rank them High, Medium or Low, or skip them.
4. **Board.** Build one HTML page of open jobs. You tick a job when you apply and remove one that is not a fit. The page goes back into the pool.
5. **Apply (optional).** Browser runners fill LinkedIn Easy Apply and company-site forms from your profile. They stop on any question your profile does not answer.

If an agent runs this for you, point it at [AGENT_GUIDE.md](AGENT_GUIDE.md).

## Requirements

| Part | Needs |
|---|---|
| Sweep, screen, read, board | Python 3.8 or newer. Standard library only, nothing to install. |
| Apply runners | Node.js 18 or newer, Google Chrome, and `npm install` in `pipeline/apply` |
| Live board on claude.ai | A Claude account with Artifacts. Optional: the board also works as a local file. |

It runs on Windows, macOS and Linux.

## Quick start

```bash
git clone https://github.com/<you>/applypilot.git
cd applypilot

python pipeline/ap.py init       # creates ./workspace with example config files
# edit workspace/config/profile.json, search.json, screening.json (see below)
python pipeline/ap.py doctor     # checks the setup and says what to fix

python pipeline/ap.py sweep --region sweden   # collect and screen (a few minutes)
python pipeline/ap.py ingest                  # put the results in the pool
python pipeline/ap.py read --batch 1          # read the survivors
python pipeline/ap.py board build             # writes workspace/dashboard/apply_board.html
```

Open `workspace/dashboard/apply_board.html` in a browser to see the board.

### Where your data lives

Everything personal goes in a **workspace** folder, never in the repository. It is `./workspace` by default and is listed in `.gitignore`. To keep it elsewhere, pass `--home <dir>` to every command or set `APPLYPILOT_HOME`.

```text
workspace/
  config/profile.json       facts about you; the form fillers answer only from this
  config/search.json        keywords and regions to sweep
  config/screening.json     rules for closing ads automatically
  dashboard/job_pool.csv    every ad ever seen, with status and reason (the record)
  dashboard/seen_index.csv  derived lookup; rebuilt automatically, never edit it
  dashboard/apply_board.html
  runs/<region>-<date>-<hour>/   raw output of each sweep
  PENDING_REVIEW.md         sweeps waiting to be ingested
  apply/                    runner results, logs, screenshots
  browser-profile/          the runners' own Chrome profile (your logins)
  data/uk_sponsor_register.csv   optional, see below
```

## Configuration

Each example file has `_comment` keys that explain every setting. A key that starts with `_` is ignored.

### profile.json

These are the facts the form fillers use. Replace every example value.

- `candidate`: your name, email, phone (also `phone_national` without the country code, which LinkedIn wants), city, links.
- `work_authorization.by_country`: for each country, set `right_to_work` and `needs_sponsorship`. `default` covers every country you do not list. This decides two things. First, whether "we do not sponsor" closes an ad. Second, how sponsorship questions on forms get answered. The answer always depends on the job's country.
- `compensation`: salary per country, as a `number` and as `text`.
- `education`, `languages`, `voluntary_self_identification`: dropdown answers. Separate alternatives with `|` and they are tried in order.
- `automation.resume_file`: the CV the runners upload. `resume_name_check` is a piece of its file name; the Easy Apply runner stops if LinkedIn shows a different resume.
- `automation.common_skills` and `years_for_common_skills`: the answer for "how many years of X". It is used only when every skill in the question is on the list.
- `automation.extra_answers`: your own `[question regex, answer]` pairs. They are checked first.

### search.json

- `keywords`: one search per keyword per location. Add keywords in the local language too. An ad has to be collected before it can be screened.
- `regions`: each region has a `name` (used on the command line), a `country` (matched against `work_authorization`) and `locations` (LinkedIn location strings). `sources` can add `"platsbanken"` for Sweden. `close_low_priority: true` closes provisional Low rows at ingest, except Easy Apply rows. `uk_sponsor_register: true` checks employers against the UK register.
- `window`: how many hours each sweep looks back. If a run is missed, the next run of that region widens the window by itself to cover the gap.

### screening.json

The patterns that decide what your field looks like: titles to exclude and include, research topics, and the words that show an ad is in your field. The example is tuned for machine learning, AI and data roles, so rewrite it for any other field. It also sets the languages you cannot work in, the most years of experience an ad may ask for (`max_years_ok`), and the internship policy.

How ads are worded is handled in code: how a language requirement is phrased, how a refusal to sponsor is phrased, how a years bar is phrased. You should not need to touch that.

## A round, step by step

```bash
python pipeline/ap.py sweep --region all     # or one region; never writes the pool
python pipeline/ap.py ingest                 # survivors -> Pending [UNREAD]; closures -> Skipped
python pipeline/ap.py read --list
python pipeline/ap.py read --batch 1         # 30 digests: requirements, years, visa signals
python pipeline/ap.py read --show 4471234567 # one ad in full
python pipeline/ap.py read --apply verdicts.csv
python pipeline/ap.py board build
python pipeline/ap.py status
```

`verdicts.csv` looks like this:

```csv
url,priority,note
https://www.linkedin.com/jobs/view/4471234567/,High,Entry level; Python and forecasting; no years bar
https://www.linkedin.com/jobs/view/4471234999/,skip,Five years of Kubernetes in production
```

Applied rows leave the unread list, so after an `--apply` the next batch to read is always `--batch 1` again.

To change rows by hand, write `key,status,reason` lines and run `python pipeline/ap.py set changes.csv`. The key is a LinkedIn job id, `pb<id>` for Platsbanken, or a URL. The status is one of Pending, Needs user, Submitted or Skipped.

The provisional priority from `ingest` measures whether you can legally take the job, not whether you fit it. Where you do not need sponsorship, every survivor starts at Medium. Where you do, an ad that offers a visa starts at High. One that offers relocation or says English is the working language starts at Medium. The rest start at Low. Reading the ad replaces this.

## The apply board

The board has these sections: Deadlines, Needs you, Easy Apply, High, Medium, Low, and Applied. Each row has a tick box and a remove button. Remove takes an optional reason, and that reason becomes the `skip_reason` in the pool. There is also a notes box for messages to your agent.

**On claude.ai (recommended).** Ask Claude Code to publish `workspace/dashboard/apply_board.html` as an Artifact that declares the `artifact` capability. The page's Save button then republishes the page with your ticks in it, so your agent can read the live page later. Keep one board at one URL forever and republish the same file. A new URL each time leaves dead boards behind with ticks on them.

**As a local file.** Open the HTML in a browser. Save downloads `apply_board.html`. Put it in `workspace/dashboard/` and sync from it.

Each round, follow this order. If you rebuild without the live copy, every tick is lost.

```bash
# 1. save the live page (artifact read, or the downloaded file) as live.html
python pipeline/ap.py board sync live.html          # ticks -> Submitted, removals -> Skipped
python pipeline/ap.py board build --live live.html  # carries the note and any unsynced ticks
# 2. republish workspace/dashboard/apply_board.html to the SAME artifact
```

## Applying (optional)

```bash
cd pipeline/apply
npm install
npm test                                   # offline check of the answer table
node login.mjs                             # log in to LinkedIn by hand, once
node easyapply.mjs ids.txt                 # dry run: fills, stops at review, saves a draft
node easyapply.mjs ids.txt --submit        # submits only when every question was known
node site_fill.mjs jobs.json               # company-site forms, dry run with screenshots
node site_fill.mjs jobs.json --submit
node inspect.mjs urls.csv                  # list a batch of forms' questions, fill nothing
```

- The runners use their own Chrome profile in `workspace/browser-profile`. Your everyday browser is untouched.
- The job's country comes from the pool. A job that is not in the pool has no country, so a sponsorship question stops the runner instead of being guessed.
- Results go to `workspace/apply/results.csv` and `site_results.csv`. Only `SUBMITTED` rows were sent. A `STOPPED` row names the question that stopped it. Either add an answer to `profile.json` or finish that application by hand.
- Easy Apply jobs that turn out to be offsite are written to `workspace/apply/offsite_urls.csv` for `site_fill`.
- **Read the terms.** LinkedIn's user agreement does not allow automated use of the site, and an account can be restricted for it. The runners go slowly, at about 45 to 90 seconds per job, and stop on LinkedIn's daily limit. You take that risk. The sweep only reads public, logged-out pages.
- Some application systems flag automated browsers as spam when you submit. Ashby is the known case. For those, do the dry run here and press submit yourself in your normal browser.

## Running it on a schedule

The sweep runs unattended. It never writes the pool, so a run that nobody reviewed cannot mark anything as screened.

**Windows (Task Scheduler):** copy `scripts/run_sweep.cmd`, set the path to Python in it, then create a task.

```bat
schtasks /Create /TN "ApplyPilot sweep sweden" /SC DAILY /ST 18:00 ^
  /TR "\"C:\path\to\applypilot\pipeline\scripts\run_sweep.cmd\" sweden"
```

In the task's settings, untick "Start the task only if the computer is on AC power". If a run is missed anyway, the next run widens its window to cover the gap.

**macOS / Linux (cron):**

```cron
0 18 * * * cd /path/to/applypilot && python3 pipeline/ap.py sweep --region sweden >> workspace/runs/cron.log 2>&1
```

Daily is the right cadence for LinkedIn. One search returns at most 100 ads. In a 24-hour window, most keywords stay under that limit. Over longer windows they hit it, and the extra ads are silently cut off.

## UK sponsor register

If you need a UK Skilled Worker visa, download the register of licensed sponsors (a CSV file) from <https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers>. Save it as `workspace/data/uk_sponsor_register.csv` and set `uk_sponsor_register: true` on the UK region. Being on the register means an employer *could* sponsor you. Being absent is the stronger signal. Matching is by name, and LinkedIn shows trading names while the register lists legal names, so check the matched name before you rely on it. To check employers by hand: `python pipeline/ap.py uk-check "Company A" "Company B"`.

## Tests

```bash
python -m unittest discover -s pipeline/tests -v
cd pipeline/apply && npm test
```

## Troubleshooting

- **"at/below the noise floor" in the sweep output.** That keyword returned no more ads than a nonsense word does. Its results are padding, not matches. Drop the keyword or make it more specific.
- **"CAP".** The keyword hit the 100-ad limit. The sweep fetches the newer half of the window again to recover some of the rest. If it keeps capping, shorten the window or split the location into cities.
- **"WALL".** LinkedIn answered with a login or challenge page instead of results. The sweep retries with backoff. If the wall persists, the run is not marked as covered, so the next run reaches back over the gap.
- **The Platsbanken request fails with a certificate error in curl.** Use Python. Git Bash's CA bundle on Windows lacks the root certificate this site uses, but Python reads the Windows certificate store. Never turn off verification.

More measured facts about job sites and application systems are in [docs/lessons.md](docs/lessons.md).
