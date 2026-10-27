// Offline checks of the answer table built from the example profile.
//   node test_answers.mjs
import fs from 'node:fs';
import path from 'node:path';
import { REPO, answerTable, pageConfig } from './lib.mjs';

const strip = o => Array.isArray(o) ? o.map(strip) : (o && typeof o === 'object')
  ? Object.fromEntries(Object.entries(o).filter(([k]) => !k.startsWith('_')).map(([k, v]) => [k, strip(v)])) : o;
const profile = strip(JSON.parse(fs.readFileSync(path.join(REPO, 'pipeline', 'config', 'profile.example.json'), 'utf8')));
const answer = (country, q) => { for (const [re, v] of answerTable(profile, country)) if (new RegExp(re, 'i').test(q)) return v; return null; };

let bad = 0;
const eq = (got, want, what) => { if (got !== want) { bad++; console.log(`FAIL ${what}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); } };
eq(answer('Sweden', 'Will you now or in the future require sponsorship?'), 'No', 'sponsorship where authorized');
eq(answer('United Kingdom', 'Will you now or in the future require sponsorship?'), 'Yes', 'sponsorship elsewhere');
eq(answer('United Kingdom', 'Do you have the right to work in the UK?'), 'No', 'right to work elsewhere');
eq(answer('Sweden', 'Are you legally authorized to work in Sweden?'), 'Yes', 'right to work where authorized');
eq(answer('', 'Will you require sponsorship?'), null, 'unknown country never answers sponsorship');
eq(answer('Germany', 'What are your salary expectations?'), '50000', 'salary by country');
eq(answer('France', 'Expected salary'), '45000', 'salary default');
eq(answer('Sweden', 'First name'), 'Robin', 'first name');
eq(answer('Sweden', 'Sign up for our newsletter'), false, 'marketing unticked');
eq(answer('Sweden', 'Keep me in your talent pool for future opportunities'), true, 'future roles ticked');
eq(answer('Sweden', 'How did you hear about us?'), 'LinkedIn', 'extra answers first');
const cfg = pageConfig(profile, 'United Kingdom', false);
eq(cfg.needsSponsorship, true, 'page config sponsorship');
eq(cfg.answers.every(([, v]) => typeof v === 'string'), true, 'page answers are strings');
console.log(bad ? `${bad} failed` : 'all answer checks passed');
process.exit(bad ? 1 : 0);
