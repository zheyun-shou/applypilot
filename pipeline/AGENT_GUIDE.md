# Agent guide: running the ApplyPilot pipeline for a user

You are an AI agent (Claude Code, Codex or similar) and a user has asked you to run their job search with this pipeline. Read this whole file before you run anything. [README.md](README.md) explains the commands; this file explains how to work.

## Your job, in one paragraph

The machines do the dull part: collecting ads, closing the obvious misfits, filling known facts into forms. You do the judgement the user would otherwise do. You read surviving ads and rank them, find the real application link, fill forms, and stop where only the user can decide. The user makes every decision that is a statement about themselves. Optimise for interviews, not for the number of applications.

## Hard rules

These come first because breaking any of them costs the user something that cannot be undone.

1. **Never invent a fact about the user.** Every answer on a form comes from `workspace/config/profile.json`, from the CV, or from the user in this conversation. If none of them covers a question, stop and ask.
2. **Never write that the user lacks a skill just because the CV does not list it.** A CV is not a complete inventory. Ask instead.
3. **A free-text question about the user stops the submission,** even when it is optional ("Why do you want to work here?", "Describe a project you are proud of"). Draft an answer, park the application as `Needs user`, and show the draft. Submit such answers yourself only if the user has explicitly allowed that kind of question, and use the wording they approved.
4. **Never log in, create an account, solve a CAPTCHA or handle 2FA.** Park the application with the exact step the user has to do.
5. **A submission counts only with evidence:** a confirmation page, a confirmation email, or the application showing in the employer's portal. Record that evidence in the pool row's notes.
6. **Never send email, messages or connection requests for the user** unless they asked for that specific message.
7. **Consent boxes:** tick privacy and data-processing consent, tick "contact me about other roles" when the profile says so, and leave marketing and newsletters unticked. The defaults are in `profile.json` under `automation`.

## First session: setup

Keep it to about ten minutes. Ask only what is needed to run safely, then do a trial.

1. `python pipeline/ap.py init`, then interview the user and fill the three config files for them. Do not hand them homework. Ask for:
   - name, email, phone, city, LinkedIn URL, and the CV file path;
   - target roles and field: rewrite `screening.json` → `title`, `content.signals`, `research.topics` for their field if it is not ML or data;
   - countries they would work in and, **for each one**, whether they have the right to work there and whether they need sponsorship. Ask for exact wording if forms should say something specific;
   - languages they can work in (the rest go in `languages.cannot_work_in`), and any language they read but do not speak (`knowledge_is_enough`);
   - the most years of experience they will try for (`years.max_years_ok`), and whether internships, graduate programmes and research posts are wanted;
   - a salary number per country. When a form asks, give a number. Answering a salary question with a question tends to end the conversation;
   - which regions and cities to sweep.
2. `python pipeline/ap.py doctor` until there is nothing left to fix.
3. Trial: one `sweep` of one region, `ingest`, read one batch, build the board. Do not apply in the trial. Show the user what was closed and why (`runs/<run>/closed_by_body.csv`), and adjust the rules if real jobs were closed.

## Every round

A round is one sitting: sync, sweep (or pick up scheduled sweeps), read, apply, publish. Start a fresh session for each round when the work is long. Keep `workspace/HANDOFF.md` so the next session can pick up. Overwrite it, do not append to it, and keep it under about 40 lines: what is open, what waits on the user, live interview processes, anything the next session must know.

1. **Read `workspace/HANDOFF.md`** and `python pipeline/ap.py status`.
2. **Sync the board first.** Fetch the live board page, save it, then run `board sync <file>`. Ticks become Submitted and removals become Skipped with the user's reason. Read the note box; it is addressed to you.
3. **Sweep** any region that has not run today: `sweep --region <name>`. Then run `ingest`. Look at the sweep summary. A keyword marked at or below the noise floor, or capped, or blocked by the wall, is a coverage problem worth one line in your report.
4. **Read every unread row**: `read --batch 1`, decide, `read --apply verdicts.csv`, repeat. See "Judging an ad" below.
5. **Apply** to what the user wants applied to (their standing instruction, or ask). See "Applying" below.
6. **Rebuild and republish the board.** Run `board build --live <the file you synced from>`. Then republish `workspace/dashboard/apply_board.html` to **the same artifact URL**, declaring the `artifact` capability. If the publish reports a conflict, the user saved in the meantime: fetch again, sync again, rebuild, then republish. Never force the publish, and never create a second board.
7. **Update `HANDOFF.md`** and report once. Write it in the user's language and keep it short: what was applied (with evidence), what is new and High, and one consolidated list of things only the user can do, one action per line.

## Judging an ad

The rules have already closed what they safely can. The provisional priority says whether the user can legally take the job, not whether they fit it. Your read decides fit.

- **High:** the role is in the user's core family, the level fits, and there is no hard blocker.
- **Medium:** an adjacent role, a stretch, or a good role with an unclear blocker, such as an ad that says nothing about sponsorship where the user needs it.
- **Low:** weak fit, but not impossible.
- **skip:** a hard blocker that the rules missed. Put the reason in the note, quoting the ad.

Things that are easy to get wrong:

- **The language an ad is written in is not a requirement.** Close on language only when the ad states it. "German is a plus" does not close anything.
- **Experience bars:** 1 to 2 years, or "a few years", usually bend. Close only above the user's `max_years_ok`.
- **Staffing agencies, consultancies and fixed-term contracts are real jobs.** Do not filter them out unless the user says so.
- **Graduate programmes and internships:** follow `screening.json`. A programme with a technical track is in scope even if its title names no technology.
- **"No longer accepting applications" on a fresh ad, or a job missing from a job board, proves nothing.** Check the employer's own careers page and the publish date before you close it.
- **Duplicates.** LinkedIn gives one ad a new id in every city. A row whose next_action starts with `CHECK:` repeats an earlier row. Confirm on the employer's site before applying twice.
- **Write notes the user could check:** quote the line in the ad that decided it.
- When the user corrects a judgement, **turn the correction into config**: a pattern in `screening.json`, an answer in `profile.json`, or a `max_years_ok` change. Then re-read the rows the old rule closed (`runs/*/closed_by_body.csv`) and reopen the ones that now pass with `ap.py set`.

## Applying

Order of preference: LinkedIn Easy Apply through the runner, then company-site forms through `site_fill`, then the user's own browser.

1. **Find the real application link.** LinkedIn hides offsite links in a redirect. The Easy Apply runner's `--triage` mode writes the real URL to `workspace/apply/offsite_urls.csv`. When the employer's own page disagrees with an aggregator's copy, the employer's page wins.
2. **Dry run first, always.** `node easyapply.mjs ids.txt` or `node site_fill.mjs jobs.json`. Read the log and the screenshot.
3. A `STOPPED` row names the question that stopped it.
   - If it is a fact the user has already given you, add it to `profile.json` → `automation.extra_answers` and run the dry run again.
   - If it is a new fact, a personal free-text question or a salary for a new country, park it as `Needs user` with the exact question.
4. `--submit` only after a clean dry run. Check `results.csv`: only `SUBMITTED` counts. `CHECK` or `UNCONFIRMED` means you look at the page yourself.
5. **Record everything** in the pool with `ap.py set`: Submitted with the evidence, or Needs user with the one action needed.
6. **Answers in the user's voice** (cover letters, why-us boxes, emails) should be short and plain. Use about 150 words, no filler and no flourish. If the user has an approved letter or paragraph, reuse its structure and wording; do not reinvent it. Many readers take em dashes and stacked colons as a sign of machine writing, so avoid them.
7. When the user's CV has several versions, use the one the profile names. The Easy Apply runner refuses to submit if LinkedIn shows a different resume.

## Park and batch

When something blocks one application, park it and move on to the next. Leave it exactly at the blocking step. Set the row to `Needs user` and write the single action needed in `next_action`, starting with `YOU:` so the board shows it in red. Do not interrupt the round for one blocker. Report all of them together at the end. If more than about eight pile up, say so instead of letting the list sprawl.

## Housekeeping the user will thank you for

- Before each round, if you have email access, archive confirmation and rejection emails from the last two days and mark them as read. Keep anything from a human and anything about a live process. Then update the pool with any rejections you found.
- Do not re-check whether old postings are still open unless the user is about to act on one.
- When a notification storm arrives (many board saves, many emails), read once at the end, not once per item.
