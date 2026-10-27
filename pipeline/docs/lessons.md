# Lessons: job sites and application systems

These facts were measured over a few months of daily use. Each one cost a silent failure before it was found. Sites change, so treat dates as "true when last checked" and re-measure when results look odd.

## LinkedIn public job search (the sweep)

- **A keyword the search cannot match does not return zero results.** It returns a generic job feed. The sweep searches the nonsense word `zzqxwv` in each location to measure this floor. Treat any keyword at or below the floor as noise. A rare keyword that hits the full 100 results is a warning sign, not a success.
- **Quotes are ignored and there is no phrase search.** Generic keywords ("algorithm engineer", "research engineer") fill the 100-result limit with unrelated jobs.
- **One search returns at most 100 ads** (10 pages of 10). A full page at offset 90 means the results were cut off.
- **There is no date-range filter, only "the last N seconds".** A missed day can only be recovered with a wider window, and wider windows hit the 100 limit on more keywords. When a search is cut off, LinkedIn keeps the 100 it ranks most relevant, not the newest.
- **The wall.** LinkedIn sometimes answers a logged-out request with a login redirect (about 800 bytes) or a JavaScript challenge (about 25 KB) instead of results. A genuinely empty answer is about 26 bytes. A counter that does not tell these apart reports a blocked search as "0 results, done". The sweep tells them apart.
- **The same ad gets a separate job id in every city** it is listed in.
- **The ad page** at `jobs-guest/jobs/api/jobPosting/<id>` holds the full description. It also shows whether the job is Easy Apply: the button has the class `apply-link-onsite`.
- **LinkedIn's location strings** take the form "City, Country" or "City, Region, Country". Metro areas sometimes have no country ("Greater Munich Metropolitan Area"). The pipeline therefore stores the country of the region that swept the ad and does not try to parse it from the location.

## Platsbanken (Sweden)

- `jobsearch.api.jobtechdev.se/search` returns an exact `total.value` and the full ad text, so there is no cap to guess at and nothing more to fetch.
- Some employers post only here, mostly public employers, small companies and staffing agencies.
- Free-text matching is as loose as LinkedIn's.
- On Windows, Git Bash's curl rejects the certificate chain because its CA bundle lacks the root. Python works. Do not turn verification off.

## Ads

- **The language an ad is written in tells you little.** Plenty of Swedish-language, Dutch-language or German-language ads work in English. Close only on a stated requirement.
- **Requirement shapes the patterns had to learn:**
  - a plain verb ("Du pratar svenska");
  - a level in brackets ("Deutsch (C1)");
  - a hyphenated compound ("Deutsch- und Englischkenntnisse");
  - a working-language clause with the noun last ("Norsk er arbeidsspråk").
- **"Knowledge of Swedish" is not "fluent Swedish".** For someone who reads a language but does not speak it, the difference decides the ad.
- **Refusing to sponsor has many shapes:**
  - "unable to offer visa sponsorship";
  - "does not meet the criteria for visa sponsorship";
  - "must already have the right to work";
  - "Visa sponsorship: can't currently sponsor".

  Each of these contains the words "visa sponsorship", so a naive "offers a visa" detector reads them as offers.
- **UK graduate schemes** often demand the right to work and offer "a limited number of sponsorships" in the next sentence. Read the whole passage before closing.
- **Public employers in Sweden** end every ad with a conditional security-vetting paragraph ("the position MAY be placed in a security class"). That is not a clearance requirement.
- **Consultancy ads** often carry a field such as "Security clearance: No".
- **A number of years in words** is often a contract length ("limited to four years"), not an experience bar. It counts as a bar only next to "at least" or "experience".
- **Dutch "jaar"** also appears in contract lengths and benefits ("na 3 jaar een sabbatical").
- **"37 hours per week" is a normal salaried job.** A dollar hourly rate is the sign of a gig platform.
- **Lowercase "intern" in Swedish means internal** ("Systemingenjör till intern IT").

## Application systems

- **LinkedIn Easy Apply:**
  - There is a daily submission limit, and the page says so when it is reached.
  - The phone field wants the national number next to a country dropdown.
  - The page shows the candidate's own location, so the job's country must come from somewhere else. A London job was once answered as if it were in the candidate's home country.
  - A stopped application can be saved as a draft from the close dialog.
- **Greenhouse:** sometimes emails an 8-character code before accepting a submission. `site_fill` waits for the code to be pasted into a file.
- **Ashby:**
  - Yes/no questions are a pair of buttons, not radio inputs.
  - Submissions from an automated browser can be rejected as spam. The same form submitted from the user's own browser goes through, and a rejected one can be tried again.
- **Teamtailor:**
  - The cookie banner has a "Decline all non-necessary" button.
  - Custom questions are named `candidate[answers_attributes]...`.
  - The CV file input is hidden.
- **Recruitee:** the phone field picks the country from the number, so type it with its + prefix.
- **Workday:** almost always requires an account, so park it for the user.
- **Hidden file inputs:** some forms hide the CV input behind a styled button. Playwright's `setInputFiles` works on hidden inputs. A browser-extension agent may need the input made visible first.
- **Resume import** ("autofill from CV") in an application system often wipes fields or merges education entries. Check every field after using it.
- **A "you have already applied" banner** on an aggregator is not proof. The proof is the employer's confirmation.
