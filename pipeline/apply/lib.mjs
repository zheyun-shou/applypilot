// Shared helpers for the apply runners: workspace paths, the profile, the
// answer table, and the job's country.
//
// THE ANSWER TABLE is a list of [question regex, answer] pairs; the first
// match wins. It is built only from profile.json. A question that matches
// nothing is never guessed: the runners stop and report it.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, '..', '..');

export function argValue(args, flag, dflt) {
  const i = args.indexOf(flag);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : dflt;
}

export function home(args = process.argv.slice(2)) {
  return path.resolve(argValue(args, '--home', process.env.APPLYPILOT_HOME || path.join(REPO, 'workspace')));
}

const strip = o => Array.isArray(o) ? o.map(strip)
  : (o && typeof o === 'object') ? Object.fromEntries(Object.entries(o).filter(([k]) => !k.startsWith('_')).map(([k, v]) => [k, strip(v)]))
  : o;

export function loadProfile(h) {
  const p = path.join(h, 'config', 'profile.json');
  if (!fs.existsSync(p)) throw new Error(`missing ${p}: run "python pipeline/ap.py init" first`);
  return strip(JSON.parse(fs.readFileSync(p, 'utf8').replace(/^﻿/, '')));
}

export function browserProfile(h) {
  return process.env.APPLYPILOT_BROWSER_PROFILE || path.join(h, 'browser-profile');
}

// Minimal CSV parsing for the pool (quoted fields, doubled quotes, newlines in quotes).
export function readCsv(file) {
  if (!fs.existsSync(file)) return [];
  const s = fs.readFileSync(file, 'utf8').replace(/^﻿/, '');
  const rows = []; let row = [], f = '', q = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (q) { if (c === '"') { if (s[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; continue; }
    if (c === '"') q = true; else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n') { row.push(f.replace(/\r$/, '')); rows.push(row); row = []; f = ''; }
    else f += c;
  }
  if (f || row.length) { row.push(f); rows.push(row); }
  const head = rows.shift() || [];
  return rows.filter(r => r.length > 1).map(r => Object.fromEntries(head.map((k, i) => [k, r[i] ?? ''])));
}

// The job's country comes from the pool, never from the page: the page also
// shows the CANDIDATE's own location, which once made a London job read as
// a job in the candidate's home country.
export function countryOf(h, jobKey) {
  const rows = readCsv(path.join(h, 'dashboard', 'job_pool.csv'));
  const r = rows.find(x => x.job_url.includes(`/jobs/view/${jobKey}/`) || x.job_url === jobKey);
  return r ? (r.country || '') : '';
}

export function authFor(profile, country) {
  const wa = profile.work_authorization || {};
  const by = wa.by_country || {};
  const k = Object.keys(by).find(n => country && n.toLowerCase() === country.toLowerCase());
  const v = k ? by[k] : (wa.default || {});
  return { known: !!country, rightToWork: !!v.right_to_work, needsSponsorship: v.needs_sponsorship !== false, describe: v.describe || '' };
}

export function salaryFor(profile, country) {
  const c = profile.compensation || {};
  const by = c.by_country || {};
  const k = Object.keys(by).find(n => country && n.toLowerCase() === country.toLowerCase());
  return (k ? by[k] : c.default) || { number: '', text: '' };
}

// Values may hold alternatives separated by |, tried in order against a
// dropdown's options. true/false mean tick/untick for checkboxes.
export function answerTable(profile, country) {
  const c = profile.candidate || {}, st = profile.current_status || {}, ed = profile.education || {};
  const au = profile.automation || {}, sid = profile.voluntary_self_identification || {};
  const auth = authFor(profile, country), sal = salaryFor(profile, country);
  const A = [...(au.extra_answers || [])];
  const add = (re, v) => { if (v !== undefined && v !== null && v !== '') A.push([re, v]); };
  add('legal name', c.legal_name);
  add('preferred (first )?name', c.preferred_name || c.first_name);
  add('first ?name|given name|^first$|voornaam|vorname', c.first_name);
  add('last ?name|surname|family name|^last$|achternaam|nachname', c.last_name);
  add('full name|^name\\b', c.legal_name);
  add('e-?mail', c.email);
  add('phone|mobile|telefon', c.phone);
  add('linkedin', c.linkedin_url);
  add('github', c.github_url);
  add('website|portfolio', c.portfolio_url || c.github_url);
  add('pronoun', c.pronouns);
  add('street|address line|^address', c.street_address);
  add('post ?code|zip', c.postal_code);
  add('^city$|location \\(city\\)|^town', c.city);
  add('^country$|country of residence', c.country);
  add('where .* (currently )?(located|based|live|reside)|current location', c.current_location);
  if (auth.known) {
    // Sponsorship questions are answered only when the job's country is known.
    add('without .*sponsor', auth.needsSponsorship ? 'No' : 'Yes');
    add('(require|need).*(visa|sponsor)|sponsor', auth.needsSponsorship ? 'Yes' : 'No');
    add('right to work|legally (authori[sz]ed|entitled|eligible)|authori[sz]ed to work|work permit|eligib', auth.rightToWork ? 'Yes' : 'No');
    add('visa.*(status|details|type)|permit details', auth.describe);
  }
  add('(salary|compensation).*(expect|desired|requirement)|expected salary|salary expectation|desired salary|^salary|gehalt|löneanspråk', sal.number);
  add('notice period|availab|earliest|start date|when .* start|uppsägning|tillträd', st.notice_period || st.available_start);
  add('current (job )?title', st.current_job_title);
  add('university|school|institution', ed.school);
  add('graduat.*year|year .*graduat', ed.graduation_year);
  add('degree|qualification', ed.degree);
  add('gender', sid.gender); add('ethnic|race', sid.ethnicity); add('disab', sid.disability);
  add('veteran', sid.veteran); add('sexual orientation', sid.sexual_orientation);
  add('^age|age (range|bracket|group)|your age', sid.age);
  add('convict|criminal', au.answer_criminal_record);
  A.push(['marketing|newsletter|promotion|advertis|sms|text message|nyhetsbrev|reklam|werbung', !!au.tick_marketing]);
  A.push(['future (job|role|position|opportunit|vacanc|recruit)|other (job|role|position|opportunit|vacanc)|talent (pool|community|network|database)|framtida|toekomstige|zukünftige', au.tick_future_roles !== false]);
  A.push(['privacy|consent|i agree|acknowledge|terms|process(ing)? (of )?(my|your)|personal data|gdpr|personuppgift|datenschutz|toestemming', true]);
  return A;
}

export function pageConfig(profile, country, submit) {
  const c = profile.candidate || {}, au = profile.automation || {}, lang = profile.languages || {};
  const auth = authFor(profile, country), sal = salaryFor(profile, country);
  return {
    submit: !!submit,
    answers: answerTable(profile, country).filter(([, v]) => typeof v === 'string'),
    skills: au.common_skills || [],
    skillYears: String(au.years_for_common_skills || '1'),
    niche: au.niche_topics || '',
    countryKnown: auth.known,
    rightToWork: auth.rightToWork,
    needsSponsorship: auth.needsSponsorship,
    country,
    phoneNational: c.phone_national || '',
    city: c.city || '',
    homeLocation: c.current_location || '',
    linkedin: c.linkedin_url || '',
    github: c.github_url || '',
    english: lang.english || 'Professional',
    otherLanguages: lang.others_default || 'None',
    salaryText: sal.text || '',
    tickFuture: au.tick_future_roles !== false,
    tickMarketing: !!au.tick_marketing,
    resumeCheck: au.resume_name_check || '',
  };
}
