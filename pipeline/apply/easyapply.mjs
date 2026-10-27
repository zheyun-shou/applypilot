// LinkedIn Easy Apply runner.
//
//   node easyapply.mjs ids.txt                dry run: fills, stops at review, saves drafts
//   node easyapply.mjs ids.txt --submit       submits when every question is known
//   node easyapply.mjs ids.txt --triage       only classify each job (Easy Apply, offsite, closed)
//   options: --max 20   --delay 45   --home <workspace>
//
// ids.txt: one LinkedIn job id (or job URL) per line; # starts a comment.
// Log in first with `node login.mjs`. It uses its own Chrome profile in
// <workspace>/browser-profile, so your everyday browser is untouched.
//
// Results append to <workspace>/apply/results.csv; the full log of each job
// is in <workspace>/apply/logs/<id>.txt. Only SUBMITTED rows were submitted.
// STOPPED rows name the question that stopped them: answer it in
// profile.json (automation.extra_answers) or finish that one by hand.
//
// LinkedIn limits Easy Apply submissions per day (the runner stops on the
// limit message). Keep the delay: fast, regular clicking looks automated.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { HERE, home, loadProfile, browserProfile, countryOf, pageConfig, argValue } from './lib.mjs';

const args = process.argv.slice(2);
const H = home(args);
const SUBMIT = args.includes('--submit');
const TRIAGE = args.includes('--triage');
const MAX = +argValue(args, '--max', 20);
const DELAY = +argValue(args, '--delay', 45);
const idsFile = args.find(a => !a.startsWith('--') && /\.txt$/.test(a));
if (!idsFile) { console.log('usage: node easyapply.mjs ids.txt [--submit|--triage] [--max N] [--delay S] [--home DIR]'); process.exit(1); }

const profile = loadProfile(H);
const ids = fs.readFileSync(idsFile, 'utf8').split(/\r?\n/).map(l => l.replace(/#.*/, '').trim())
  .map(l => (l.match(/(\d{8,})/) || [])[1]).filter(Boolean);
const pageSrc = fs.readFileSync(path.join(HERE, 'easy_apply_page.js'), 'utf8');
const OUTDIR = path.join(H, 'apply');
const LOGS = path.join(OUTDIR, 'logs');
fs.mkdirSync(LOGS, { recursive: true });
const OUT = path.join(OUTDIR, 'results.csv');
if (!fs.existsSync(OUT)) fs.writeFileSync(OUT, 'time,jobid,mode,status,detail\n');
const q = s => '"' + String(s).replace(/"/g, '""').replace(/\s+/g, ' ').slice(0, 300) + '"';
const record = (id, status, detail) => {
  fs.appendFileSync(OUT, [new Date().toISOString(), id, SUBMIT ? 'submit' : 'dry', status, q(detail)].join(',') + '\n');
  console.log(`  ${status}  ${String(detail).split('\n')[0].slice(0, 120)}`);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const isLogin = u => /login|authwall|checkpoint|signup|uas\//.test(u);

const ctx = await chromium.launchPersistentContext(browserProfile(H), { channel: 'chrome', headless: false, viewport: null });
const page = ctx.pages()[0] || await ctx.newPage();
await page.goto('https://www.linkedin.com/feed/');
await sleep(4000);
if (isLogin(page.url())) {
  console.log('Not logged in. Run "node login.mjs" first, or log in in this window (waiting 10 min)...');
  for (let t = 0; t < 120 && isLogin(page.url()); t++) await sleep(5000);
  if (isLogin(page.url())) { await ctx.close(); process.exit(2); }
}

let n = 0;
try {
  for (const id of ids) {
    if (n >= MAX) { console.log(`--max ${MAX} reached`); break; }
    console.log(`[${n + 1}] ${id}`);
    try {
      await page.goto(`https://www.linkedin.com/jobs/view/${id}/`, { waitUntil: 'domcontentloaded' });
      await sleep(6000);
      const body = await page.innerText('body');
      if (/reached today.s Easy Apply limit/i.test(body)) { record(id, 'LIMIT', 'daily Easy Apply limit'); break; }
      if (/No longer accepting applications/i.test(body)) { record(id, 'CLOSED', 'no longer accepting'); continue; }
      if (/Applied \d|Application submitted/i.test(body.slice(0, 6000))) { record(id, 'ALREADY', 'already applied'); continue; }
      // Ask LinkedIn how this job is applied to, so an offsite job is never
      // mistaken for a broken button. The offsite URL is kept for site_fill.
      const meta = await page.evaluate(async jid => {
        const t = (document.cookie.match(/JSESSIONID="?([^";]+)/) || [])[1];
        const r = await fetch('/voyager/api/jobs/jobPostings/' + jid, { headers: { 'csrf-token': t } });
        if (!r.ok) return { err: r.status };
        const j = await r.json(), am = j.applyMethod || {}, first = Object.values(am)[0] || {};
        return { state: j.jobState, method: Object.keys(am).map(k => k.split('.').pop()).join(','), url: first.companyApplyUrl || '' };
      }, id).catch(e => ({ err: e.message }));
      if (meta.state && meta.state !== 'LISTED') { record(id, 'CLOSED', 'jobState ' + meta.state); continue; }
      if (meta.method && !/OnsiteApply/.test(meta.method)) {
        record(id, 'NOT_EA', 'offsite ' + meta.url);
        fs.appendFileSync(path.join(OUTDIR, 'offsite_urls.csv'), id + ',' + meta.url + '\n');
        continue;
      }
      if (TRIAGE) { record(id, 'EA', meta.method || JSON.stringify(meta)); await sleep(1500); continue; }
      const country = countryOf(H, id);
      const cfg = pageConfig(profile, country, SUBMIT);
      const log = String(await page.evaluate(`(async () => { ${pageSrc}\n return await easyApply(${JSON.stringify(cfg)}); })()`));
      fs.writeFileSync(path.join(LOGS, `${id}.txt`), `country from pool: ${country || '(unknown - sponsorship questions will stop)'}\n${log}`);
      if (/reached today.s Easy Apply limit/i.test(await page.innerText('body'))) { record(id, 'LIMIT', 'daily Easy Apply limit'); break; }
      const stop = (log.match(/STOP[^\n]*(\n[^\n]*){0,3}/) || [''])[0];
      const status = /SUBMIT: Application submitted/.test(log) ? 'SUBMITTED'
        : /SUBMIT: NOT CONFIRMED/.test(log) ? 'CHECK'
        : stop ? 'STOPPED' : /^STATUS|NO EASY APPLY/.test(log) ? 'SKIPPED' : SUBMIT ? 'CHECK' : 'DRY_OK';
      record(id, status, stop || log.split('\n').slice(-2).join(' | '));
      n++;
    } catch (e) {
      record(id, 'ERROR', e.message);
    }
    await sleep((DELAY + Math.random() * DELAY) * 1000);
  }
} finally {
  console.log(`done; see ${OUT}`);
  await ctx.close().catch(() => {});
  process.exit(0);   // the browser context can keep node alive otherwise
}
