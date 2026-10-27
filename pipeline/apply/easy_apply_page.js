// Runs INSIDE a LinkedIn job page (easyapply.mjs injects it with a CFG object
// built from profile.json). Walks the Easy Apply dialog page by page, answers
// only what CFG covers, and stops on the first unknown question. On a stop it
// closes the dialog and saves it as a draft, so a human can finish it.
//
// Returns a plain-text log. Lines starting with STOP explain why it stopped;
// "SUBMIT: Application submitted" is the only proof of a submission.
async function easyApply(CFG) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const visibleButtons = () => [...document.querySelectorAll('button')].filter(b => b.offsetParent);
  const button = text => visibleButtons().find(b => b.textContent.trim() === text);
  const dialogText = () => {
    const t = document.body.innerText, i = t.indexOf('Apply to');
    if (i < 0) return '';
    const d = t.slice(i, i + 6000), j = d.search(/\n(Next|Review|Submit application)\n/);
    return j > 0 ? d.slice(0, j) : d;
  };
  const setValue = (el, v) => {
    const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype
      : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const labelFor = e => document.querySelector('label[for="' + e.id + '"]');
  const click = e => (e.closest('[role=radio]') || labelFor(e) || e).click();
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const SKILL = CFG.skills.length ? new RegExp('^(' + CFG.skills.map(esc).join('|') + ')$', 'i') : null;
  const NICHE = CFG.niche ? new RegExp(CFG.niche, 'i') : /$^/;
  const MARKETING = /marketing|newsletter|nyhetsbrev|promotion|advertis|reklam|news and offers|product updates|commercial communication|Werbung/i;
  const FUTURE = /future (job|role|position|opportunit|vacanc|recruit)|other (job|role|position|opportunit|vacanc)|talent (pool|community|network|database)|framtida|andra tjänster|andere (functies|vacatures|Stellen)|toekomstige|zukünftige/i;
  const CONSENT = /consent|privacy|gdpr|personal data|data processing|toestemming|Einwilligung|Datenschutz/i;

  const known = q => {
    for (const [re, v] of CFG.answers) if (new RegExp(re, 'i').test(q)) return v;
    return null;
  };

  // Yes/no questions. Sponsorship and right-to-work are answered only when
  // the job's country is known; experience questions get Yes unless the topic
  // is niche or the bar is three years or more.
  function yesNo(q) {
    if (/convict|criminal|offen[cs]e/i.test(q)) return null;
    if (/sponsor|visa|permit|right to work|authori[sz]|eligib/i.test(q)) {
      if (!CFG.countryKnown) return null;
      if (/without[^?]*sponsor/i.test(q)) return CFG.needsSponsorship ? 'No' : 'Yes';
      if (/sponsor/i.test(q)) return CFG.needsSponsorship ? 'Yes' : 'No';
      return CFG.rightToWork ? 'Yes' : 'No';
    }
    if (/clearance|vetting|licen[cs]e|driv|citizen|passport|degree in|PhD|doctor/i.test(q)) return null;
    if (/\b(1|2|one|two)\+? years?/i.test(q) && /(experience|worked|professional)/i.test(q) && !NICHE.test(q)) return 'Yes';
    if (/\d\+? years|\b(three|four|five|six|seven|eight|ten)\+? years/i.test(q)) return null;
    if (/^(have you|do you have|are you (experienced|familiar|comfortable|proficient)|can you|did you)\b/i.test(q.trim())
        && /(experience|built|build|developed|develop|written|wrote|worked|work with|deployed|shipped|maintained|used|designed|implemented|trained|familiar|knowledge|proficien|hands-on)/i.test(q)
        && !NICHE.test(q)) return 'Yes';
    if (CFG.city && new RegExp('(live|living|located|based|reside)\\b.*\\b(in|near|around)\\b.*\\b' + esc(CFG.city) + '\\b', 'i').test(q)) return 'Yes';
    return null;
  }

  const questionOf = e => {
    if (e.type === 'radio') {
      const rr = e.closest('[role=radio]');
      if (rr && rr.getAttribute('aria-label')) return rr.getAttribute('aria-label').trim();
    }
    if (e.type === 'radio' || e.type === 'checkbox') {
      const fs = e.closest('fieldset');
      const lg = fs && fs.querySelector('legend');
      if (lg) return lg.textContent.trim().replace(/\s+/g, ' ');
    }
    const l = e.id && labelFor(e);
    return l && l.textContent.trim() ? l.textContent.trim().replace(/\s+/g, ' ') : (e.getAttribute('aria-label') || '').trim();
  };
  const optionOf = e => {
    const rr = e.closest('[role=radio]');
    if (rr) return rr.textContent.trim();
    return ((labelFor(e) || {}).textContent || '').trim();
  };
  const pickOption = (opts, want) => String(want).split('|').map(w => opts.find(o => o.toLowerCase().startsWith(w.toLowerCase()))).find(Boolean);
  const yearsQuestion = q => {
    const m = q.match(/(?:years|jaar|Jahre)[^?]*?(?:with|in|met|mit) (.+?)\s*\??\*?$/i);
    if (!m || !SKILL) return false;
    return m[1].replace(/\s*\(.*?\)\s*/g, '').split(/\s*(?:,|\/|\bor\b|\band\b|&)\s*/i).filter(Boolean).every(x => SKILL.test(x.trim()));
  };

  function answerPage() {
    const unknown = [], done = [], groups = {};
    const fields = [...document.querySelectorAll('input,select,textarea')].filter(e =>
      e.offsetParent && e.type !== 'hidden' && e.type !== 'tel' && !/search|language/i.test(e.id + e.name)
      && !(e.tagName === 'SELECT' && e.options.length > 60));
    for (const e of fields) {
      const q = questionOf(e);
      if (!q || /\.(pdf|docx?)$/i.test(q)) continue;
      if (e.type === 'radio') { (groups[q] = groups[q] || []).push(e); continue; }
      if (e.type === 'checkbox') {
        if (/follow|alert for similar/i.test(q)) continue;
        const both = q + ' ' + optionOf(e);
        if (MARKETING.test(both)) { if (e.checked !== CFG.tickMarketing) click(e); done.push('marketing ' + CFG.tickMarketing); continue; }
        if (FUTURE.test(both)) { if (e.checked !== CFG.tickFuture) click(e); done.push('future roles ' + CFG.tickFuture); continue; }
        if (CONSENT.test(both)) { if (!e.checked) click(e); done.push('consent'); continue; }
        if (e.checked) continue;
        unknown.push('CHECKBOX ' + q + ' :: ' + optionOf(e));
        continue;
      }
      if (e.tagName === 'SELECT') {
        const opts = [...e.options].map(o => o.text.trim());
        let want = known(q);
        if (want === null) {
          if (/english|engels|englisch/i.test(q)) want = CFG.english;
          else if (/(swedish|dutch|german|danish|norwegian|finnish|french|zweeds|nederlands|deutsch|duits)/i.test(q) && /proficien|level|niveau|kenntnis|vaardig/i.test(q)) want = CFG.otherLanguages;
          else if (opts.includes('Yes') && opts.includes('No')) want = yesNo(q);
        }
        const hit = want && pickOption(opts, want);
        if (hit) { const o = [...e.options].find(o => o.text.trim() === hit); if (e.value !== o.value) setValue(e, o.value); done.push(q + '=' + hit); continue; }
        if (e.selectedOptions[0] && !/^Select/.test(e.selectedOptions[0].text)) continue;
        unknown.push('SELECT ' + q + ' [' + opts.join('/') + ']');
        continue;
      }
      // text and textarea
      // LinkedIn's phone box sits next to a country-code dropdown and wants the national number.
      let v = /mobile phone|phone number/i.test(q) && CFG.phoneNational ? CFG.phoneNational : known(q);
      if (v === null && /linkedin/i.test(q)) v = CFG.linkedin;
      if (v === null && /github/i.test(q)) v = CFG.github;
      if (v === null && /current location|where are you (currently )?(based|located)/i.test(q)) v = CFG.homeLocation;
      if (v === null && yearsQuestion(q)) v = CFG.skillYears;
      if (v === null && /salary|compensation/i.test(q) && e.tagName === 'TEXTAREA') v = CFG.salaryText;
      if (v !== null && v !== '') { v = String(v).split('|')[0]; if (e.value !== v) setValue(e, v); done.push(q + '=' + v); continue; }
      if (e.value) continue;
      if (!e.required && /^photo$|middle name|^cover letter$/i.test(q)) continue;
      unknown.push((e.tagName === 'TEXTAREA' ? 'TEXTAREA ' : 'TEXT ') + q);
    }
    for (const q in groups) {
      const g = groups[q];
      const labels = g.map(optionOf).map(x => ({ Ja: 'Yes', Nee: 'No', Nein: 'No', Nej: 'No' }[x] || x));
      let a = known(q);
      if (!a || !pickOption(labels, a)) a = yesNo(q);
      const hit = a && pickOption(labels, a);
      if (hit) { const k = labels.indexOf(hit); if (!g[k].checked) click(g[k]); done.push(q + '=' + hit); continue; }
      if (g.some(r => r.checked)) continue;
      unknown.push('RADIO ' + q + ' [' + labels.join('/') + ']');
    }
    return { unknown, done };
  }

  const log = [];
  const state = (document.body.innerText.match(/Applied \d[^\n]*|Application submitted[^\n]*|No longer accepting[^\n]*/) || [''])[0];
  if (state) return 'STATUS ' + state;
  const start = [...document.querySelectorAll('button,a')].find(b => b.offsetParent && /^(Easy Apply|Continue)$/.test(b.textContent.trim()));
  if (!start) return 'NO EASY APPLY BUTTON';
  if (!dialogText()) { start.click(); await sleep(3500); if (!dialogText()) { start.click(); await sleep(4500); } }
  const resumeOk = text => !CFG.resumeCheck || text.includes(CFG.resumeCheck);
  for (let step = 0; step < 10; step++) {
    const d = dialogText();
    if (!d) { log.push('STOP no dialog'); break; }
    if (/Review your application/.test(d)) {
      if (!resumeOk(d)) { log.push('STOP the review page shows a resume other than ' + CFG.resumeCheck); break; }
      if (CFG.submit && button('Submit application')) {
        button('Submit application').click(); await sleep(3500);
        log.push('SUBMIT: ' + ((document.body.innerText.match(/Application submitted/) || ['NOT CONFIRMED'])[0]));
      } else log.push('DRY: reached the review page');
      break;
    }
    const tel = [...document.querySelectorAll('input[type=tel]')].find(e => e.offsetParent);
    if (tel && !tel.value && CFG.phoneNational) { setValue(tel, CFG.phoneNational); log.push('phone set'); }
    const city = [...document.querySelectorAll('input')].find(x => x.offsetParent && /city or location/i.test(x.placeholder || ''));
    if (city && !city.value && CFG.city) {
      city.focus(); setValue(city, CFG.city); await sleep(2500);
      const op = [...document.querySelectorAll('[role=option]')].find(x => x.offsetParent && x.textContent.includes(CFG.city));
      if (op) { op.click(); await sleep(800); log.push('city set'); }
    }
    const body = d.replace(/^Apply to[^\n]*/, '');
    if (/Resume/.test(body) && !resumeOk(body)) { log.push('STOP resume page does not show ' + CFG.resumeCheck); break; }
    const { unknown, done } = answerPage();
    if (done.length) log.push('answered: ' + done.join(' | '));
    if (unknown.length) { log.push('STOP unknown:\n' + unknown.join('\n')); break; }
    const next = button('Next') || button('Review');
    if (!next) {
      if (CFG.submit && button('Submit application')) {
        button('Submit application').click(); await sleep(3500);
        log.push('SUBMIT: ' + ((document.body.innerText.match(/Application submitted/) || ['NOT CONFIRMED'])[0]));
      } else log.push((CFG.submit ? 'STOP' : 'DRY') + ' no Next button; buttons: ' + visibleButtons().map(b => b.textContent.trim()).filter(s => s && s.length < 30).slice(0, 10).join('|'));
      break;
    }
    next.click(); await sleep(2300);
    const err = (document.body.innerText.match(/Invalid input|Please (enter|make)[^\n]*|is required[^\n]*|Enter a (whole|decimal) number[^\n]*/) || [''])[0];
    if (err && dialogText() === d) { log.push('STOP validation: ' + err); break; }
    if (step === 9) log.push('STOP too many pages');
  }
  // Leave a stopped or dry-run application as a draft for a human.
  if (/STOP|DRY/.test(log.join('\n')) && dialogText()) {
    const x = visibleButtons().find(b => /Dismiss/i.test(b.getAttribute('aria-label') || ''));
    if (x) { x.click(); await sleep(1500); if (button('Save')) { button('Save').click(); await sleep(1000); log.push('(draft saved)'); } }
  }
  return log.join('\n') || 'EMPTY LOG';
}
