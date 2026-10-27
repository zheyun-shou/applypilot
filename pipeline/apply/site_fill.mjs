// Fill company-site application forms (Greenhouse, Lever, Ashby, Workable,
// Teamtailor, Recruitee, SmartRecruiters and most hand-built forms) by
// question text, from profile.json.
//
//   node site_fill.mjs jobs.json            dry run: fill, screenshot, never submit; tabs stay open
//   node site_fill.mjs jobs.json --submit   submit only when no required field is left unknown
//   options: --only id1,id2   --home <workspace>
//
// jobs.json: [{ "id": "4471234567", "url": "https://...", "country": "United Kingdom",
//               "extra": [["regex", "answer"], ...], "why": "text for a why-us box",
//               "click": "regex of a button to press first", "frame": "regex of the form's iframe url",
//               "steps": [["click", "selector"], ["type", "selector", "text"], ["key", "Enter"],
//                         ["select", "selector", "option text"]] }]
// country is optional when the job is in the pool (looked up by id).
// A job's own extra answers win over the profile. A why-us box is filled
// only from "why"; without it the runner stops there, by design.
//
// Results append to <workspace>/apply/site_results.csv, screenshots to
// <workspace>/apply/shots/. Lines starting with ?? are what stopped a job.
//
// Some ATSs (Ashby in particular) flag automated browsers as spam on
// submit. For those, run the dry run here and submit from your own browser.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { home, loadProfile, browserProfile, countryOf, answerTable, argValue } from './lib.mjs';

const args = process.argv.slice(2);
const H = home(args);
const SUBMIT = args.includes('--submit');
const ONLY = argValue(args, '--only', null);
const jobsFile = args.find(a => a.endsWith('.json'));
if (!jobsFile) { console.log('usage: node site_fill.mjs jobs.json [--submit] [--only id,id] [--home DIR]'); process.exit(1); }
const jobs = JSON.parse(fs.readFileSync(jobsFile, 'utf8')).filter(j => !ONLY || ONLY.split(',').includes(String(j.id)));
const profile = loadProfile(H);
const CV = (profile.automation || {}).resume_file;
if (!CV || !fs.existsSync(CV)) { console.log(`resume_file not found: ${CV} (set automation.resume_file in profile.json)`); process.exit(1); }
const OUTDIR = path.join(H, 'apply');
const OUT = path.join(OUTDIR, 'site_results.csv');
const SHOTS = path.join(OUTDIR, 'shots');
fs.mkdirSync(SHOTS, { recursive: true });
fs.mkdirSync(path.join(OUTDIR, 'logs'), { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

const LABEL = () => {
  window.__lab = e => {
    const byFor = e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`);
    const leg = e.closest('fieldset')?.querySelector('legend');
    const grp = e.closest('[role=group],[role=radiogroup],.field,.form-group,.application-question,[class*=question],[class*=Field]');
    let t = (e.type === 'radio' || e.type === 'checkbox') ? ((leg && leg.innerText) || (grp && grp.innerText.split('\n')[0]) || '') : '';
    // a radio's group often carries only a section header; climb to the nearest line that reads like a question
    if (e.type === 'radio' && !/\?/.test(t)) { let p = e.parentElement; for (let k = 0; p && k < 7; k++, p = p.parentElement) { const qs = p.innerText.split('\n').filter(s => /\?\s*\*?\s*$/.test(s.trim())); if (qs.length === 1) { t = qs[0]; break; } if (qs.length > 1) break; } }
    if (!t) t = (byFor && byFor.innerText) || e.getAttribute('aria-label') || (e.getAttribute('aria-labelledby') && document.getElementById(e.getAttribute('aria-labelledby'))?.innerText) || (e.closest('label') || {}).innerText || (grp && grp.innerText.split('\n')[0]) || e.name || e.placeholder || '';
    return t.replace(/\s+/g, ' ').replace(/\*|\(required\)|Required/gi, '').trim();
  };
  window.__opt = e => ((e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`)?.innerText) || e.closest('label')?.innerText || e.value || '').replace(/\s+/g, ' ').trim();
};

async function fillFrame(f, A, why, page) {
  await f.evaluate(LABEL);
  const fields = await f.evaluate(() => [...document.querySelectorAll('input,textarea,select')]
    .filter(e => !['hidden', 'submit', 'button', 'search'].includes(e.type) && !/recaptcha|cookie/i.test(e.name + e.id) && (e.offsetParent || e.type === 'file' || e.type === 'radio' || e.type === 'checkbox'))
    .map((e, i) => { e.setAttribute('data-sf', i); return { i, tag: e.tagName, type: e.type, q: __lab(e), opt: __opt(e), req: e.required || e.getAttribute('aria-required') === 'true', combo: e.getAttribute('role') === 'combobox' || !!e.closest('[class*=select__control]'), name: e.name, val: e.type === 'checkbox' || e.type === 'radio' ? e.checked : e.value }; }));
  const log = [];
  const pick = q => { for (const [r, v] of A) if (new RegExp(r, 'i').test(q)) return v; return undefined; };
  const doneRadio = new Set();
  for (const x of fields) {
    const sel = `[data-sf="${x.i}"]`;
    if (x.type === 'file') {
      if (/cover|additional|other|portfolio|sample/i.test(x.q + x.name)) continue;
      if (/resume|cv|r.sum/i.test(x.q + x.name) || fields.filter(y => y.type === 'file').indexOf(x) === 0) { await f.setInputFiles(sel, CV).catch(e => log.push('FILE ERR ' + e.message.slice(0, 60))); log.push('FILE CV'); await sleep(2500); }
      continue;
    }
    let v = /why|motivat|interest(s|ed) you|what attracts/i.test(x.q) && x.tag === 'TEXTAREA' && why ? why : pick(x.q);
    if (x.type === 'checkbox') {
      if (typeof v === 'string' && /^yes$/i.test(v)) v = true;
      if (typeof v !== 'boolean') { const o = pick(x.opt); if (typeof o === 'boolean') v = o; }
      if (v === true && !x.val) await f.evaluate(s => { const e = document.querySelector(s); const l = e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`); (e.offsetParent ? e : (l || e.closest('label') || e)).click(); }, sel).catch(() => {});
      if (v === false && x.val) await f.evaluate(s => { const e = document.querySelector(s); const l = e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`); (e.offsetParent ? e : (l || e.closest('label') || e)).click(); }, sel).catch(() => {});
      if (typeof v === 'boolean') log.push(`CB ${x.opt.slice(0, 50)} = ${v}`); else if (x.req) log.push(`?? REQ CHECKBOX ${x.q.slice(0, 60)} :: ${x.opt.slice(0, 50)}`);
      continue;
    }
    if (x.type === 'radio') {
      if (doneRadio.has(x.name)) continue;
      if (v === undefined || typeof v === 'boolean') { if (!fields.some(y => y.name === x.name && y.val)) log.push(`?? RADIO ${x.q.slice(0, 80)} [${fields.filter(y => y.name === x.name).map(y => y.opt).join('/')}]`); doneRadio.add(x.name); continue; }
      const g = fields.filter(y => y.name === x.name);
      const hit = g.find(y => String(v).split('|').some(s => y.opt.toLowerCase().startsWith(s.toLowerCase())));
      if (hit) { if (!hit.val) await f.evaluate(s => { const e = document.querySelector(s); const l = e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`); (e.offsetParent ? e : (l || e.closest('label') || e)).click(); }, `[data-sf="${hit.i}"]`).catch(() => {}); log.push(`RADIO ${x.q.slice(0, 60)} = ${hit.opt}`); }
      else log.push(`?? RADIO ${x.q.slice(0, 80)} no option for ${v} [${g.map(y => y.opt).join('/')}]`);
      doneRadio.add(x.name); continue;
    }
    if (v === '') continue;
    if (v === undefined || typeof v === 'boolean') { if (!x.val) log.push(`${x.req ? '?? REQ' : '-- opt'} ${x.tag} ${x.q.slice(0, 110)}`); continue; }
    if (x.tag === 'SELECT') {
      const ok = await f.evaluate(([s, v]) => { const e = document.querySelector(s); const o = [...e.options].find(o => v.split('|').some(t => o.text.trim().toLowerCase().startsWith(t.toLowerCase()))); if (!o) return [...e.options].map(o => o.text.trim()).join('/'); e.value = o.value; e.dispatchEvent(new Event('change', { bubbles: true })); return true; }, [sel, String(v)]);
      log.push(ok === true ? `SELECT ${x.q.slice(0, 60)} = ${v}` : `?? SELECT ${x.q.slice(0, 60)} no option for ${v} [${String(ok).slice(0, 200)}]`);
      continue;
    }
    if (x.combo) {
      let done = false;
      for (const s of String(v).split('|')) {
        await f.click(sel, { force: true }).catch(() => {}); await f.fill(sel, '').catch(() => {}); await f.type(sel, s, { delay: 30 }).catch(() => {}); await sleep(1200);
        const opt = f.locator('[role=option]:visible, [class*=select__option]:visible').filter({ hasText: new RegExp(s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i') }).first();
        if (await opt.count()) { const t = await opt.innerText(); await opt.click().catch(() => {}); log.push(`COMBO ${x.q.slice(0, 60)} = ${t.slice(0, 40)}`); done = true; break; }
      }
      if (!done) { await f.fill(sel, '').catch(() => {}); log.push(`?? COMBO ${x.q.slice(0, 80)} no option for ${v}`); }
      await page.keyboard.press('Escape').catch(() => {});
      continue;
    }
    v = String(v).split('|')[0];
    if (x.val && x.val === v) continue;
    await f.fill(sel, v).catch(e => log.push('ERR ' + e.message.slice(0, 60)));
    log.push(`TEXT ${x.q.slice(0, 60)} = ${String(v).slice(0, 50)}`);
  }
  // Ashby yes/no questions are a pair of buttons, not radios
  const yn = await f.evaluate(() => [...document.querySelectorAll('button')].filter(b => b.innerText.trim() === 'Yes' && b.nextElementSibling?.innerText.trim() === 'No')
    .map((b, k) => { b.setAttribute('data-yn', k); let p = b.parentElement, q = ''; for (let i = 0; p && i < 5 && !q; i++, p = p.parentElement) q = (p.querySelector('label')?.innerText || ''); return { k, q: q.replace(/\s+/g, ' ').replace(/\*/g, '').trim(), on: /active|selected|checked/i.test(b.className + b.nextElementSibling.className) || b.getAttribute('aria-pressed') === 'true' || b.nextElementSibling.getAttribute('aria-pressed') === 'true' }; })).catch(() => []);
  for (const b of yn) {
    if (b.on) continue;
    const v = (A.find(([r, v]) => typeof v === 'string' && /^(yes|no)/i.test(v) && new RegExp(r, 'i').test(b.q)) || [])[1];
    if (typeof v !== 'string' || !/^(yes|no)/i.test(v)) { log.push(`?? REQ YESNO ${b.q.slice(0, 100)}`); continue; }
    const yes = /^yes/i.test(v);
    await f.evaluate(([k, yes]) => { const b = document.querySelector(`[data-yn="${k}"]`); (yes ? b : b.nextElementSibling).click(); }, [b.k, yes]).catch(() => {});
    log.push(`YESNO ${b.q.slice(0, 60)} = ${yes ? 'Yes' : 'No'}`);
  }
  return log;
}

const ctx = await chromium.launchPersistentContext(browserProfile(H), { channel: 'chrome', headless: false, viewport: null });
if (!fs.existsSync(OUT)) fs.writeFileSync(OUT, 'time,jobid,mode,status,detail\n');
for (const j of jobs) {
  console.log(j.id);
  const page = await ctx.newPage();
  page.setDefaultTimeout(8000);
  const lines = [];
  let status = 'DRY_OK';
  try {
    await page.goto(j.url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await sleep(5000);
    for (const t of [/decline all|reject all|only necessary|necessary only|decline/i]) { const b = page.locator('button:visible', { hasText: t }).first(); if (await b.count()) { await b.click().catch(() => {}); await sleep(800); } }
    if (j.click) { const b = page.locator('a:visible, button:visible', { hasText: new RegExp(j.click, 'i') }).first(); if (await b.count()) { await b.click().catch(() => {}); await sleep(5000); } }
    const vis = async () => page.evaluate(() => [...document.querySelectorAll('input,textarea')].filter(e => e.offsetParent && !['hidden', 'search', 'checkbox'].includes(e.type)).length).catch(() => 0);
    if (!j.click && (await vis()) < 3) { const b = page.locator('a:visible, button:visible', { hasText: /^\s*(apply( now| for this (job|position|role)| here)?|i'?m interested)\s*$/i }).first(); if (await b.count()) { await b.click().catch(() => {}); await sleep(5000); } }
    const A = [...(j.extra || []), ...answerTable(profile, j.country || countryOf(H, String(j.id)))];
    for (const f of page.frames()) {
      if (j.frame && !new RegExp(j.frame).test(f.url())) continue;
      const n = await f.evaluate(() => document.querySelectorAll('input:not([type=hidden]),textarea').length).catch(() => 0);
      if (n < 3) continue;
      lines.push(...await fillFrame(f, A, j.why, page));
    }
    // second pass catches fields that appear after earlier answers
    await sleep(1500);
    for (const f of page.frames()) {
      if (j.frame && !new RegExp(j.frame).test(f.url())) continue;
      const n = await f.evaluate(() => document.querySelectorAll('input:not([type=hidden]),textarea').length).catch(() => 0);
      if (n < 3) continue;
      const again = (await fillFrame(f, A, j.why, page)).filter(l => !/^FILE/.test(l));
      lines.push(...again.filter(l => /^\?\?/.test(l)).map(l => 'PASS2 ' + l));
    }
    // per-site steps for custom widgets: [["click", "css or text=..."], ["type", "selector", "text"], ["key", "Enter"]]
    for (const s of j.steps || []) {
      if (s[0] === 'click') await page.locator(s[1]).first().click({ timeout: 5000 }).catch(e => lines.push('STEP ERR ' + s[1] + ' ' + e.message.slice(0, 60)));
      if (s[0] === 'type') await page.locator(s[1]).first().fill(s[2]).catch(e => lines.push('STEP ERR ' + s[1]));
      if (s[0] === 'key') await page.keyboard.press(s[1]).catch(() => {});
      if (s[0] === 'select') for (const f of page.frames()) { const l = f.locator(s[1]); if (await l.count()) { const opts = await l.first().evaluate(e => [...e.options].map(o => o.text.trim())); const o = opts.find(t => t.toLowerCase() === s[2].toLowerCase()) || opts.find(t => t.toLowerCase().startsWith(s[2].toLowerCase())); if (o) { await l.first().selectOption({ label: o }, { force: true }).catch(e => lines.push('STEP ERR ' + e.message.slice(0, 60))); lines.push(`STEP select ${s[1]} = ${o}`); } else lines.push(`STEP ERR no option ${s[2]} in [${opts.join('/')}]`); break; } }
      await sleep(1200);
    }
    await page.screenshot({ path: path.join(SHOTS, `${j.id}.png`), fullPage: true }).catch(() => {});
    const missing = [...new Set(lines.filter(l => /^PASS2 \?\?/.test(l)))];
    if (missing.length) status = 'STOPPED';
    if (SUBMIT && !missing.length) {
      let sent = false;
      // most specific label first; "apply" alone often hits the page's own "Apply for this job" button
      const tries = [/submit (my )?application/i, /^\s*submit\s*$/i, /send application|^\s*send\s*$/i, /^\s*apply( now)?\s*$/i];
      outer: for (const re of tries) for (const f of page.frames()) {
        if (j.frame && !new RegExp(j.frame).test(f.url())) continue;
        const b = f.locator('button:visible, a[role=button]:visible, [type=submit]:visible', { hasText: re }).last();
        if (await b.count()) { await b.scrollIntoViewIfNeeded().catch(() => {}); await b.click({ timeout: 4000 }).catch(() => b.evaluate(e => e.click())); sent = true; break outer; }
      }
      if (!sent) for (const f of page.frames()) {
        const b2 = f.locator('input[type=submit]:visible').last();
        if (await b2.count()) { await b2.evaluate(e => e.click()); sent = true; break; }
      }
      await sleep(8000);
      // Greenhouse may email an 8-character code. Paste it into
      // <workspace>/apply/codes/<id>.txt within 7.5 minutes and the runner types it.
      for (const f of page.frames()) {
        const t = await f.evaluate(() => document.body.innerText).catch(() => '');
        if (!/verification code was sent/i.test(t)) continue;
        const cf = path.join(OUTDIR, 'codes', `${j.id}.txt`);
        fs.mkdirSync(path.dirname(cf), { recursive: true });
        console.log(`WAITING_CODE ${j.id} since ${new Date().toISOString()}`);
        let code = '';
        for (let k = 0; k < 90 && !code; k++) { await sleep(5000); if (fs.existsSync(cf)) code = fs.readFileSync(cf, 'utf8').trim(); }
        if (!code) { lines.push('?? no verification code arrived'); break; }
        const boxes = f.locator('input[id^="security-input"], input[maxlength="1"]:visible');
        const n = await boxes.count();
        if (n >= 8) for (let k = 0; k < 8; k++) await boxes.nth(k).fill(code[k]);
        else await f.locator('input[name*="security"], input[id*="security"]').first().fill(code).catch(() => {});
        await sleep(800);
        await f.locator('button:visible', { hasText: /submit/i }).last().evaluate(e => e.click()).catch(() => {});
        lines.push('CODE entered');
        await sleep(8000);
        break;
      }
      const body = (await page.innerText('body').catch(() => '')).slice(0, 3000);
      const frameText = (await Promise.all(page.frames().map(f => f.evaluate(() => document.body.innerText.slice(0, 2000)).catch(() => '')))).join(' ');
      const ok = /thank you|thanks for applying|application (has been )?(received|submitted|sent)|we.ve received|successfully/i.test(body + frameText) && !/couldn.t submit|flagged as possible spam/i.test(body + frameText);
      status = !sent ? 'NO_BUTTON' : ok ? 'SUBMITTED' : 'UNCONFIRMED';
      if (!ok) for (const f of page.frames()) {
        const errs = await f.evaluate(() => [...document.querySelectorAll('[aria-invalid=true], .error, [class*=error], [class*=Error], [role=alert]')].filter(e => e.offsetParent && e.innerText && e.innerText.length < 200).map(e => e.innerText.trim() || (e.name || e.id)).slice(0, 8)).catch(() => []);
        if (errs.length) lines.push('?? ERRORS ' + errs.join(' / '));
      }
      lines.push('AFTER: ' + (body + ' ' + frameText).replace(/\s+/g, ' ').slice(0, 300));
      await page.screenshot({ path: path.join(SHOTS, `${j.id}_after.png`), fullPage: true }).catch(() => {});
    }
  } catch (e) { status = 'ERROR'; lines.push(e.message.slice(0, 200)); }
  fs.writeFileSync(path.join(OUTDIR, 'logs', `site_${j.id}.txt`), lines.join('\n'));
  fs.appendFileSync(OUT, [new Date().toISOString(), j.id, SUBMIT ? 'submit' : 'dry', status, '"' + lines.filter(l => /^(PASS2 )?\?\?|AFTER/.test(l)).join(' | ').replace(/"/g, "'").slice(0, 600) + '"'].join(',') + '\n');
  if (!SUBMIT) continue; // dry: leave the tab open for a look
  await page.close().catch(() => {});
}
if (SUBMIT) await ctx.close();
else { console.log('dry run done; tabs left open. Ctrl+C to close.'); await sleep(5000); await ctx.close(); }
