// List the questions on company-site application forms without filling
// anything. Use it to see what a batch of forms will ask before a dry run.
//   node inspect.mjs urls.csv [--home <workspace>]     (lines: jobid,url)
// Output: <workspace>/apply/forms.jsonl, one JSON object per form.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { home, browserProfile } from './lib.mjs';

const args = process.argv.slice(2);
const H = home(args);
const file = args.find(a => a.endsWith('.csv'));
if (!file) { console.log('usage: node inspect.mjs urls.csv [--home DIR]'); process.exit(1); }
const rows = fs.readFileSync(file, 'utf8').split(/\r?\n/).filter(Boolean)
  .map(l => [l.slice(0, l.indexOf(',')), l.slice(l.indexOf(',') + 1)]);
fs.mkdirSync(path.join(H, 'apply'), { recursive: true });
const OUT = path.join(H, 'apply', 'forms.jsonl');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const ctx = await chromium.launchPersistentContext(browserProfile(H), { channel: 'chrome', headless: false, viewport: null });

const collect = () => {
  const lab = e => {
    const id = e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`);
    const t = (id && id.innerText) || e.getAttribute('aria-label') || (e.closest('label') || {}).innerText
      || ((e.closest('fieldset,.field,.form-group,[class*=question],[class*=field]') || {}).innerText || '').split('\n')[0] || e.name || e.placeholder || '';
    return t.replace(/\s+/g, ' ').trim().slice(0, 160);
  };
  const els = [...document.querySelectorAll('input,textarea,select')].filter(e => !['hidden', 'submit', 'button'].includes(e.type));
  return {
    url: location.href,
    fields: els.map(e => `${e.tagName === 'TEXTAREA' ? 'TEXTAREA' : e.tagName === 'SELECT' ? 'SELECT' : (e.type || 'text').toUpperCase()}${e.required || e.getAttribute('aria-required') === 'true' ? '*' : ''} ${lab(e)}`),
  };
};

for (const [id, url] of rows) {
  console.log(id);
  const rec = { id, url };
  const page = await ctx.newPage();
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(5000);
    let r = await page.evaluate(collect);
    if (r.fields.length < 4) {
      const b = page.locator('a:visible, button:visible', { hasText: /^\s*(apply( now| for this job| here)?|i'?m interested)\s*$/i }).first();
      if (await b.count()) { await b.click().catch(() => {}); await sleep(5000); r = await page.evaluate(collect); }
    }
    for (const f of page.frames()) {
      if (f === page.mainFrame()) continue;
      try { const x = await f.evaluate(collect); if (x.fields.length > 3) r.fields.push(...x.fields.map(s => 'IFRAME ' + s)); } catch {}
    }
    Object.assign(rec, r);
  } catch (e) { rec.err = e.message.slice(0, 200); }
  fs.appendFileSync(OUT, JSON.stringify(rec) + '\n');
  await page.close().catch(() => {});
}
await ctx.close();
console.log('wrote ' + OUT);
