// Open the runners' own Chrome profile on LinkedIn's login page and wait (up
// to 30 minutes) for you to log in by hand. Run once; the session is kept in
// <workspace>/browser-profile. The runners never type passwords or solve
// CAPTCHAs.
//   node login.mjs [--home <workspace>] [--url https://other-site/login]
import { chromium } from 'playwright-core';
import { home, browserProfile, argValue } from './lib.mjs';

const args = process.argv.slice(2);
const url = argValue(args, '--url', 'https://www.linkedin.com/login/');
const ctx = await chromium.launchPersistentContext(browserProfile(home(args)), { channel: 'chrome', headless: false, viewport: null });
const p = ctx.pages()[0] || await ctx.newPage();
await p.goto(url);
await p.bringToFront();
const waiting = () => /login|authwall|checkpoint|signup|uas\/|signin/i.test(p.url());
console.log('Log in in the Chrome window. Waiting...');
for (let t = 0; t < 360 && waiting(); t++) await new Promise(r => setTimeout(r, 5000));
console.log(waiting() ? 'still on a login page; giving up' : 'logged in: ' + p.url());
await new Promise(r => setTimeout(r, 3000));
await ctx.close();
