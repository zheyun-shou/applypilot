# ApplyPilot

A job search workflow for AI agents such as Claude Code and Codex.

ApplyPilot has two parts.

- **The skill** (`SKILL.md`, `references/`, `templates/`) tells an agent how to run a job search with you. It covers your profile, screening rules, resume choice, filling forms safely and recording every outcome.
- **The pipeline** (`pipeline/`) does the repetitive work. It collects new ads every day, closes the ones that cannot work for you and gives each one a reason, keeps every ad in one pool, builds an apply board you tick, and can fill application forms from your profile.

You can use the skill alone. The pipeline is optional, and it is the part that saves the most time.

## What the pipeline adds

- **Daily sweeps.** It collects new ads from LinkedIn's public job search, which needs no login, and from Platsbanken for Sweden. A missed run is covered by the next one, because the window widens to fill the gap. It warns you when a keyword returns only padding or hits LinkedIn's 100-ad limit.
- **Screening by rule, with a reason for every ad it closes.** It closes ads only for things you cannot change. That means a language you do not work in, a refusal to sponsor in a country where you need sponsorship, a security clearance, a years bar above your level, or gig work. Your field and limits go in config files. How ads phrase these things is handled in code and covered by tests.
- **One job pool.** Every ad it has seen is in `job_pool.csv` with a status and a reason, so nothing is screened twice and nothing gets lost.
- **Reading in batches.** The ads that pass are shown to you or your agent as short digests of requirements, years and visa signals, 30 at a time. You rank each one High, Medium or Low, or skip it.
- **An apply board.** One HTML page lists the open jobs by priority, with deadlines and the jobs that need you at the top. You tick a job when you apply and remove one that is not a fit, and those changes go back into the pool. It works as a local file. It can also be a claude.ai Artifact that saves your ticks, so your agent can read them later.
- **Form runners (optional).** Node scripts fill LinkedIn Easy Apply and company-site forms using only `profile.json`. Sponsorship answers follow the job's country. A dry run is the default. They stop on any question your profile does not answer. With `--submit` they submit only when every question was known.
- **A UK sponsor check.** It can match employers against the UK register of licensed sponsors.
- **A guide for agents.** [pipeline/AGENT_GUIDE.md](pipeline/AGENT_GUIDE.md) gives the rules an agent follows when it runs your search. It never invents a fact about you. It stops on personal free-text questions. It never logs in for you. It counts a submission only when there is evidence.

## Your data stays on your computer

Everything personal goes in a `workspace/` folder. That includes your profile, CV path, job pool, board, browser logins and run logs. The folder is in `.gitignore`, so it is never committed. The repository holds only code, templates and a fake example person.

Connectors such as Gmail belong to your own agent account, not to this repository. Someone who clones the repository gets none of your data, memory or email.

## Install

Clone the repository:

```bash
git clone https://github.com/zheyun-shou/applypilot.git
```

To use it as a skill, put it in your agent's skills folder.

```bash
# Claude Code
git clone https://github.com/zheyun-shou/applypilot.git ~/.claude/skills/applypilot

# Codex
git clone https://github.com/zheyun-shou/applypilot.git ~/.codex/skills/applypilot
```

Then open a new session and say:

```text
Use the applypilot skill to set up my job search. Start with a trial that only finds and sorts jobs and does not apply to anything.
```

To update, run `git pull` in that folder.

## Quick start for the pipeline

The sweep, screening, pool and board need only Python 3.8 or newer. The form runners also need Node.js 18 or newer and Chrome.

```bash
cd applypilot
python pipeline/ap.py init                    # creates ./workspace with example config
# fill in workspace/config/profile.json, search.json, screening.json
python pipeline/ap.py doctor                  # says what is missing
python pipeline/ap.py sweep --region sweden   # collect and screen
python pipeline/ap.py ingest                  # add the results to the pool
python pipeline/ap.py read --batch 1          # read the ads that passed
python pipeline/ap.py board build             # writes workspace/dashboard/apply_board.html
```

Or ask your agent to run it for you: "Read pipeline/AGENT_GUIDE.md and set up the ApplyPilot pipeline for me." It will ask you about ten minutes of questions and fill the config files itself.

Full commands, config fields, scheduling and troubleshooting are in [pipeline/README.md](pipeline/README.md).

## How the skill works

Setup builds five things from `templates/`. The agent drafts them by asking you questions, so you do not fill them by hand.

- **Candidate profile.** Facts the agent must never guess, such as your identity, contact details, work authorization, target roles, location and salary.
- **Application rules.** What to prioritise, what to skip, and what to hand back to you.
- **Resume routing.** Which CV to use for which kind of role.
- **Answer bank.** True, reusable answers to common form questions.
- **Dashboard.** CSV sheets for jobs, applications, blockers and follow-ups.

Every job gets a status.

- `Pending` means worth a look or an application later.
- `Needs user` means a fact or action only you can give, such as sponsorship, salary, a login or a personal answer.
- `Skipped` means not worth applying under your rules, with the reason recorded.
- `Submitted` means sent, with evidence such as a confirmation page or email.

There are two resume modes. **Volume** is the default. It uses a few fixed CV versions and short forms. **Precision** is for a role you care about. It tailors the CV from an editable source, such as DOCX, Markdown or plain text, and you review it before anything is sent.

[examples/fake-demo-example](examples/fake-demo-example) shows a complete setup for a person who does not exist.

## Safety rules

ApplyPilot never:

- guesses legal, identity, work authorization, salary or employment facts;
- makes up experience, credentials or documents;
- gets past CAPTCHA, Cloudflare or other bot checks, or logs in through an account or 2FA it does not know;
- counts a saved job or an autofill badge as an application;
- publishes CVs, contact details, immigration documents, application history, cookies or one-time codes.

A dry run is the default. Nothing is submitted until you allow it. LinkedIn's user agreement does not allow automated use, so the Easy Apply runner puts your account at some risk. The sweep reads only public pages. Some application systems, Ashby for example, flag automated browsers as spam. For those, do the dry run with the runner and press submit yourself.

## Status

The skill comes from [yvonnehe772/applypilot](https://github.com/yvonnehe772/applypilot) by Yvonne He. This repository adds the pipeline. The screening examples are tuned for ML, AI and data roles in Europe. Change `screening.json` for your own field. Issues and suggestions are welcome.
