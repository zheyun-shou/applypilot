# -*- coding: utf-8 -*-
"""Rule-based screening. Two stages, cheapest first:

    title_ok(title)            decides whether the ad body is worth fetching
    Screener.verdict(text, …)  reads the body; returns None to keep, or the
                               reason the ad is closed

Every closure carries its reason, so a run is auditable and a closed ad is
never read twice. The rules close only on things the candidate cannot change:
a language they do not work in, a right-to-work refusal where they need
sponsorship, a clearance or citizenship demand, a years bar above their level,
gig work. Fit is left to a human (or an agent) reading the survivors.

What the field means (ML, data, design, nursing...) lives in screening.json,
not here. The patterns in this file are about how ads are WRITTEN: how a
language requirement is phrased, how a refusal to sponsor is phrased, how a
years bar is phrased. They took many real ads to get right; the comments say
which shapes each one exists for.
"""
import copy, io, json, os, re

from . import config

FLAGS = re.I


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_rules(overrides=None):
    """Example defaults, overlaid with the workspace's screening.json."""
    with io.open(os.path.join(config.EXAMPLES, 'screening.example.json'), encoding='utf-8') as f:
        base = config._strip_comments(json.load(f))
    if overrides is None:
        overrides = config.screening()
    return _merge(base, overrides)


# ============================================================== languages
# A language counts as REQUIRED only when the ad says so: the language word
# next to a word about speaking, writing, knowing or being fluent in it, or a
# native-language compound that can only mean the requirement. The language an
# ad is written in is not a requirement, and neither is "German market" or
# "our Danish customers".
LANG_REQ = {
    'swedish': (
        r'flytande svenska|svenska och engelska|engelska och svenska|'
        r'goda kunskaper i svenska|behärskar svenska|talar och skriver svenska|'
        r'fluent (in )?swedish|swedish and english|english and swedish|proficiency in swedish|'
        r'swedish language|kommunicera\w* .{0,25}svenska|svenska i tal och skrift|'
        r'god svenska|svenska språket|obehindrat på svenska|svenska obehindrat|'
        # a plain verb clause ("Du pratar svenska") and the krav wordings
        r'du pratar svenska|pratar du svenska|talar svenska|kunskaper i svenska|'
        r'svenska (är|ar) ett krav|krav på svenska|svenska krävs|speak swedish|'
        # "fluency in English is required, along with fluency in either Swedish or Norwegian"
        r'fluen(t|cy) in [^.]{0,30}swedish|swedish or norwegian|norwegian or swedish|'
        r'scandinavian language|native swedish|swedish native speaker|modersm(a|å)l'),
    'german': (
        r'deutsch-?\s*kenntnisse|verhandlungssicher\w*\s+deutsch|deutsch\w*\s+in\s+wort'
        r'|flie(ss|ß)end\w*\s+deutsch|sehr\s+gute?\s+deutsch|gute?\s+deutschkenntnisse'
        r'|deutsch\s*(\([^)]{0,25}\))?\s*(und|sowie)\s+englisch|englisch\s+und\s+deutsch'
        # hyphenated compound: "sicheren Deutsch- und Englischkenntnissen"
        r'|deutsch-\s*(und|sowie)\s+englisch|\bsicher\w*\s+deutsch(?!land)'
        # any inflection of gut right before the language; \b keeps Deutschland out
        r'|(sehr\s+)?gute\w*\s+deutsch\b'
        # a level in brackets, an "in" before the language, the -fähigkeiten noun
        r'|flie(ss|ß)end\w*\s+in\s+deutsch|deutsch\s*\(\s*(min\.?\s*)?(level\s*)?[abc][12]'
        r'|(kenntnisse|f(ae|ä)higkeiten|kommunikation\w*)\s+in\s+deutsch'
        r'|german\s+(language|skills?|proficiency|fluency)'
        r'|fluen(t|cy)\s+(in\s+)?(business\s+)?german|speak\w*\s+german'
        r'|german\s+(and|&)\s+english|english\s+(and|&)\s+german'
        r'|(good|strong|excellent|native|professional)\s+(command\s+of\s+)?german'
        r'|german\s+at\s+(least\s+)?[abc][12]|[abc][12]\s+level\s+(in\s+)?german'
        r'|native\s+german|german\s+native\s+speaker|muttersprach\w*'),
    'danish': (
        r'flydende\s+dansk|dansk\s+i\s+(skrift|tale)|taler\s+dansk|p(a|å)\s+dansk'
        r'|danish\s+(language|skills?|proficiency|fluency)'
        r'|fluen(t|cy)\s+(in\s+)?[^.]{0,30}danish|speak\w*\s+danish'
        r'|danish\s+(and|&)\s+english|english\s+(and|&)\s+danish'
        r'|danish\s+at\s+(least\s+)?[abc][12]|[abc][12]\s+level\s+(in\s+)?danish'
        r'|native\s+danish|danish\s+native\s+speaker|scandinavian language'),
    'norwegian': (
        r'flytende\s+norsk|beherske\w*\s+norsk|god\s+norsk|norsk\s+(skriftlig|muntlig)'
        r'|norwegian\s+(language|skills?|proficiency|fluency)'
        r'|fluen(t|cy)\s+(in\s+)?[^.]{0,30}norwegian|speak\w*\s+norwegian'
        r'|norwegian\s+(and|&)\s+english|english\s+(and|&)\s+norwegian'
        r'|norwegian\s+at\s+(least\s+)?[abc][12]|[abc][12]\s+level\s+(in\s+)?norwegian'
        r'|native\s+norwegian|norwegian\s+native\s+speaker|scandinavian language'),
    'finnish': (
        r'suomen\s+kiel|sujuva\w*\s+suome|suomea\s+(ja|sek(a|ä))'
        # the conjunction can sit between suomen and kielen
        r'|suomen\s+ja\s+englannin|sek(a|ä)\s+suomi\s+ett(a|ä)\s+englanti'
        r'|finnish\s+(language|skills?|proficiency|fluency)'
        r'|fluen(t|cy)\s+(in\s+)?finnish|speak\w*\s+finnish'
        r'|finnish\s+(and|&)\s+english|english\s+(and|&)\s+finnish'
        r'|finnish\s+at\s+(least\s+)?[abc][12]|[abc][12]\s+level\s+(in\s+)?finnish'
        r'|native\s+finnish|finnish\s+native\s+speaker'),
    'dutch': (
        r'vloeiend\w*\s+(in\s+(het\s+)?)?nederlands|nederlands\s+(en|&)\s+engels'
        r'|engels\s+(en|&)\s+nederlands|nederlandse\s+taal|beheersing\s+van\s+het\s+nederlands'
        r'|nederlandstalig|(goed|uitstekend)\w*\s+nederlands\b'
        # the conjunction splits Nederlandse from taal
        r'|nederlandse\s+(en|&)\s+engelse\s+taal|engelse\s+(en|&)\s+nederlandse\s+taal'
        r'|zowel\s+(de\s+|het\s+)?nederlands\w*\s+als'
        r'|beheers\w*\s+(van\s+)?(de\s+|het\s+)?nederlands|nederlands\s+sprekend'
        r'|(native|near-native)(\s+level)?(\s+or\s+near-native(\s+level)?)?\s+dutch'
        r'|dutch\s+(language|skills?|proficiency|fluency)'
        r'|fluen(t|cy)\s+(in\s+)?(business\s+)?dutch|speak\w*\s+dutch'
        r'|dutch\s+(and|&)\s+english|english\s+(and|&)\s+dutch'
        r'|(good|strong|excellent|native|professional)\s+(command\s+of\s+)?dutch'
        r'|dutch\s+at\s+(least\s+)?[abc][12]|[abc][12]\s+level\s+(in\s+)?dutch|moedertaal'),
    'french': (
        r'fran(ç|c)ais\s+(courant|indispensable|exig)|ma(î|i)trise\s+du\s+fran(ç|c)ais'
        r'|french\s+(language|skills?|proficiency|fluency)|fluen(t|cy)\s+(in\s+)?french'
        r'|speak\w*\s+french|french\s+(and|&)\s+english|english\s+(and|&)\s+french'
        r'|native\s+french|french\s+at\s+(least\s+)?[abc][12]|langue\s+maternelle'),
}
# The working-language clause, read as a clause: "The working language is
# German" closes; "Working language is English, German is a plus" must not.
# It reaches 40 characters back because some languages put the noun last
# ("Norsk er arbeidsspråk").
LANG_WORD = {
    'swedish': r'swedish|svenska', 'german': r'german|deutsch', 'danish': r'danish|dansk',
    'norwegian': r'norwegian|norsk', 'finnish': r'finnish|suomi', 'dutch': r'dutch|nederlands',
    'french': r'french|fran(ç|c)ais',
}
WORK_CLAUSE = re.compile(
    r'[^.;\n]{0,40}(?:working language|company language|office language|arbeitssprache|'
    r'arbetsspr(?:a|å)k|koncernspr(?:a|å)k|arbeidsspr(?:a|å)k|voertaal|werktaal|langue de travail)'
    r'[^.;\n]{0,90}', FLAGS)
ENGLISH_WORD = re.compile(r'english|englisch|engelsk|engels|engelska|anglais', FLAGS)

# A language named as a bonus is not a bar. The softener must sit on the SAME
# LINE and in the same sentence as the language: a wider window reads "French
# is an advantage" as softening the German demanded two lines up, and a
# following "Nice to have" heading as softening the line above it.
SOFT_AFTER = re.compile(
    r'^[^\n]{0,24}?\b(is|are|would be|w(ae|ä)re[n]?|sind|ist|är|ar)?\s*'
    r'(a |an |ett )?(plus|nice to have|advantage|advantageous|asset|bonus|'
    r'desirable|beneficial|optional|von vorteil|w(ue|ü)nschenswert|meriterande|merit|'
    r'een\s+pr(e|é)|pr(e|é)\b|pluspunt)', FLAGS)
SOFT_BEFORE = re.compile(
    r'(or if possible|if possible|optionally|preferably|ideally|meriterande|'
    r'(is|are) a plus:?|nice to have:?|bonus:?)[\s,]{0,4}$', FLAGS)
# "knowledge of X" without any speaking or fluency word. Used for languages the
# candidate can read and follow but not work in.
LANG_SPEAK = re.compile(
    r'\btala\w*|\btalar\b|\btal\b|muntlig|prata\w*|kommunicera\w*|flytande|obehindrat|'
    r'fluen\w*|speak\w*|spoken|verbal|communicat\w*|arbetsspr|'
    r'mycket goda|very good|excellent|utmärkt|utmarkt|native|modersm', FLAGS)
LANG_KNOW = re.compile(r'kunskap\w*|knowledge|kännedom|kannedom|kenntnis\w*|kennis', FLAGS)


def _sentence(text, start, end):
    a = max(text.rfind(c, 0, start) for c in '.;\n')
    ends = [i for i in (text.find(c, end) for c in '.;\n') if i != -1]
    return text[a + 1: min(ends) if ends else len(text)]


def _softened(text, m):
    tail = text[m.end():m.end() + 60]
    cut = min([i for i in (tail.find('\n'), tail.find('.'), tail.find(';')) if i != -1] or [len(tail)])
    ls = text.rfind('\n', 0, m.start())
    head = text[ls + 1 if ls != -1 else 0: m.start()]
    return bool(SOFT_AFTER.match(tail[:cut]) or SOFT_BEFORE.search(head))


# ======================================================== right to work
# An ad that refuses sponsorship, or demands a right to work the candidate
# lacks. Every shape below was seen in a real ad and missed by the one before
# it: "unable to OFFER sponsorship", "does not meet the criteria for visa
# sponsorship", "must already have THE right to work", an adverb between the
# negator and the verb ("can't currently sponsor").
NO_SPONSOR = re.compile(
    r'(not\s+(be\s+)?(able\s+to\s+)?sponsor|cannot\s+sponsor|unable\s+to\s+sponsor'
    r'|no\s+(visa\s+)?sponsorship|without\s+sponsorship|sponsorship\s+is\s+not'
    r'|we\s+do\s+not\s+(provide|offer)\s+(visa|work\s+permit)'
    r'|unable\s+to\s+(offer|provide|support|consider)[^.\n]{0,60}?sponsor'
    r'|(do(es)?\s+not|cannot|can\'?t|will\s+not|won\'?t)\s+(offer|provide|support)'
    r'[^.\n]{0,40}?sponsorship'
    r'|not\s+meet\s+the\s+criteria\s+for[^.\n]{0,25}?sponsorship'
    r'|must\s+(already\s+)?(have|hold)\s+(a|the)?\s*(valid\s+|unrestricted\s+)?'
    r'(eu|eea|schengen)?\s*(work\s+(permit|authoriz|authoris)|right\s+to\s+work)'
    r'|unrestricted\s+right\s+to\s+work'
    r'|only\s+considering\s+candidates\s+with[^.\n]{0,20}right\s+to\s+work'
    r'|entitled\s+to\s+work\s+in[^.\n]{0,40}(with\s+)?legal\s+work\s+authoriz'
    r'|(and\s+)?the\s+legal\s+right\s+to\s+work\s+in'
    r'|without\s+requiring[^.\n]{0,25}?sponsorship'
    r'|not\s+eligible\s+for[^.\n]{0,40}?sponsorship'
    r'|(eu|eea)\s+(work\s+)?(authoriz|authoris)ation\s+(is\s+)?required'
    r'|legally\s+authorized\s+to\s+work|arbeitserlaubnis\s+erforderlich'
    r'|(cannot|can\'?t|unable\s+to|not\s+able\s+to|do(es)?\s+not|will\s+not|won\'?t)'
    r'\s+(currently|presently|at\s+this\s+time|at\s+present)\s+(offer|provide|support|sponsor)'
    r'|(cannot|can\'?t|unable\s+to|not\s+able\s+to)\s+sponsor\s+(at\s+this\s+time|at\s+present|currently))',
    FLAGS)
# The carve-out: many graduate schemes say "you must have the right to work by
# the time you join" and then offer a limited number of sponsorships in the
# next sentence. A right-to-work demand closes only when no offer follows.
SPONSOR_OFFER = re.compile(
    r'(visa\s+sponsorships?\s+(are\s+)?available|sponsorship\s+will\s+be\s+considered'
    r'|we\s+(can\s+|do\s+|may\s+)?(offer|provide|sponsor)[^.\n]{0,30}?'
    r'(visa\s+sponsorship|sponsorship|work\s+permit)'
    r'|we\s+are\s+(a\s+)?(licen[cs]ed|registered)\s+sponsor'
    r'|able\s+to\s+sponsor|happy\s+to\s+sponsor|will\s+sponsor)', FLAGS)
SPONSOR_VISA = re.compile(
    r'(visa\s+sponsorship|sponsor\s+(your\s+)?(visa|work\s+permit)'
    r'|we\s+(help|assist|support)\s+(you\s+)?with\s+(your\s+)?(visa|work\s+permit)'
    r'|work\s+permit\s+application|visum\w*\s+unterst(u|ü)tz|arbeitserlaubnis\w*\s+unterst(u|ü)tz)', FLAGS)
SPONSOR_RELO = re.compile(
    r'(relocation\s+(support|package|assistance|help|allowance)'
    r'|we\s+(help|assist)\s+with\s+(your\s+)?relocation'
    r'|umzugs(hilfe|kosten|unterst(u|ü)tzung|pauschale))', FLAGS)
# "...relocation support is not provided" and "Visa sponsorship: can't
# currently sponsor" contain the offer words and mean the opposite.
SPONSOR_NEG = re.compile(
    r'^[^.\n]{0,60}?\b(is|are)\s+not\s+(provided|offered|available)'
    r'|^[^.\n]{0,60}?\bno[t]?\s+(provided|offered|available)'
    r'|^[^.\n]{0,60}?\b(cannot|can\'?t|unable\s+to|not\s+able\s+to)\b', FLAGS)
SPONSOR_NEG_BEFORE = re.compile(
    r'\b(no|not|never|unable|cannot|can\'?t|without|un(?:willing|likely))\b[^.\n]{0,60}$', FLAGS)
ENGLISH_ONLY = re.compile(
    r'(english\s+is\s+our\s+(working|company|office)\s+language'
    r'|our\s+(working|company|office)\s+language\s+is\s+english'
    r'|we\s+(work|communicate)\s+in\s+english|all\s+communication\s+is\s+in\s+english'
    r'|english\s+only|no\s+\w+\s+(language\s+)?required'
    r'|(german|deutsch|dutch|nederlands|swedish|svenska|danish|norwegian|finnish)'
    r'(\s+language)?(\s+skills)?(\s+(is|are|would\s+be))?(\s+een)?\s+(a\s+|an\s+)?'
    r'(plus|advantage|bonus|nice[\s-]to[\s-]have|beneficial|not\s+required|pr(e|é)|pluspunt))', FLAGS)

# Clearance and citizenship. Public employers in some countries end every ad
# with a CONDITIONAL security paragraph ("the position MAY be placed in a
# security class; if so, a vetting is done"). That states a possibility, not a
# requirement, so a match inside such a sentence does not close.
CLEARANCE = re.compile(
    r'(swedish citizen|säkerhetsprövning|sakerhetsprovning|security clearance|'
    # Bare "medborgarskap" is not enough: "om du har ett medborgarskap utanför
    # EU/EES" is an ID-paperwork note on an open ad.
    r'svenskt medborgarskap|citizenship (is )?required|'
    r'\b(sc|dv|nato secret) clearance|staatsangeh(ö|o)rigkeit)', FLAGS)
CONDITIONAL = re.compile(
    r'kan f(o|ö)rekomma|om s(a|å) (a|ä)r fallet|i dessa fall|may be placed in a security class|'
    r'if (this|that) is the case|may be required to undergo|kan bli aktuell|kan komma att|'
    r'may be subject to', FLAGS)
# Consultancy ads often carry a field "Security clearance: No".
CLEARANCE_NOT = re.compile(r'^\s*:?\s*(no|not required|none|nej|n/a)(?![a-z])', FLAGS)

# ============================================================ years bar
# A bar is not always flush against the unit ("4-8 or more years"), and is
# often written in words ("at least five years"). A span of years in words is
# usually a CONTRACT length ("limited to four years"), so a word-form bar counts
# only with a minimum cue before it or "experience" after it.
YEARS = re.compile(
    r'(\d+)\s*\+?\s*(?:[-–]\s*\d+\s*)?(?:\(?(?:or|eller|oder)\s+(?:more|mer|fler|mehr)\)?\s+)?'
    r'(?:years|års|ars|yrs|jahren?)\b', FLAGS)
WORD_N = {'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
          'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'fifteen': 15,
          'två': 2, 'tva': 2, 'tre': 3, 'fyra': 4, 'fem': 5, 'sex': 6, 'sju': 7, 'atta': 8,
          'åtta': 8, 'nio': 9, 'tio': 10,
          'zwei': 2, 'drei': 3, 'vier': 4, 'fünf': 5, 'fuenf': 5, 'sechs': 6, 'sieben': 7,
          'acht': 8, 'neun': 9, 'zehn': 10}
WORD_YEARS = re.compile(
    r'\b(' + '|'.join(sorted(WORD_N, key=len, reverse=True)) + r')\s+(?:\+\s*)?(?:or more\s+)?'
    r'(?:years|års|ars|yrs|jahren?)\b', FLAGS)
YEAR_MIN_CUE = re.compile(r'(at least|minimum|minst|more than|over|\bmin\.?|mindestens|mind\.)\s*$', FLAGS)
YEAR_EXP_CUE = re.compile(r'^\s*(of\s+|av\s+)?[\w-]{0,18}\s*'
                          r'(experience|erfarenhet|arbetslivserfarenhet|praxis|erfahrung)', FLAGS)
# Dutch "jaar" also carries contract and benefit lengths, so it always needs a cue.
DUTCH_YEARS = re.compile(
    r'(minimaal|minstens|ten\s+minste|minimum|min\.)?\s*(\d+)\s*\+?\s*'
    r'(?:(?:[-–]|tot)\s*\d+\s*)?jaar\b([^.\n]{0,40})', FLAGS)
DUTCH_WORD_N = {'twee': 2, 'drie': 3, 'vier': 4, 'vijf': 5, 'zes': 6, 'zeven': 7, 'acht': 8,
                'negen': 9, 'tien': 10}
DUTCH_WORD_YEARS = re.compile(
    r'(minimaal|minstens|ten\s+minste)?\s*\b(twee|drie|vier|vijf|zes|zeven|acht|negen|tien)'
    r'\s+jaar\b([^.\n]{0,40})', FLAGS)
DUTCH_EXP = re.compile(r'(werk)?ervaring|experience', FLAGS)


def years_bar(text, floor=1):
    """Lowest stated years bar in floor..15, or None."""
    bars = [int(y) for y in YEARS.findall(text) if floor <= int(y) <= 15]
    for m in DUTCH_YEARS.finditer(text):
        n = int(m.group(2))
        if floor <= n <= 15 and (m.group(1) or DUTCH_EXP.search(m.group(3))):
            bars.append(n)
    for m in DUTCH_WORD_YEARS.finditer(text):
        n = DUTCH_WORD_N[m.group(2).lower()]
        if n >= floor and (m.group(1) or DUTCH_EXP.search(m.group(3))):
            bars.append(n)
    for m in WORD_YEARS.finditer(text):
        n = WORD_N.get(m.group(1).lower())
        if n is None or n < floor:
            continue
        if (YEAR_MIN_CUE.search(text[max(0, m.start() - 30):m.start()])
                or YEAR_EXP_CUE.match(text[m.end():m.end() + 40])):
            bars.append(n)
    return min(bars) if bars else None


# ================================================================ other
# Gig platforms and freelance brokerages clear every other filter. A dollar
# hourly rate is the reliable tell. "37 hours per week" is NOT one: salaried
# jobs state contracted hours too.
GIG = re.compile(r'(\$\s?\d+(\.\d+)?\s*(/|per )\s?(hr|hour)|task-based|f-skatt|timpris|'
                 r'target rate|egen firma)', FLAGS)
# Seniority stated without a number.
SENIOR_PROSE = re.compile(r'(deep expertise|extensive experience|mentor(ing)? junior|lead complex|'
                          r'drive team-wide|proven ability to lead|several years|seasoned)', FLAGS)

# Internships. English "Intern" is matched case-sensitively because lowercase
# "intern" is an adjective in Swedish ("Systemingenjör till intern IT").
INTERN_EN = re.compile(r'\bIntern(s|ship|ships)?\b')
INTERN_OTHER = re.compile(r'\b(internship|internships|praktik|praktikant|praktikplats|werkstudent|stage)\b', FLAGS)
CONVERSION = re.compile(
    r'(possibilit(y|ies)|opportunity|chance|potential|option|view|intention|aim)'
    r'[^.;\n]{0,60}(permanent|full[- ]time|tillsvidare|fast anst|continue|stay on|'
    r'join (the team|us) (full|permanently|after))'
    r'|(lead|leads|leading|convert|converts|converted|conversion|transition)'
    r'[^.;\n]{0,40}(permanent|full[- ]time|employment|anst(a|ä)llning)'
    r'|return offer|full[- ]time (position|role|offer|employment)[^.;\n]{0,30}'
    r'(after|upon|following|at the end)'
    r'|m(o|ö)jlighet till (fast |en |tillsvidare)?anst(a|ä)llning'
    r'|chans till (fast |en )?anst(a|ä)llning'
    r'|kan leda till (en )?(fast |tillsvidare)?anst(a|ä)llning'
    r'|med sikte p(a|å) anst(a|ä)llning|path to (a )?(permanent|full[- ]time)', FLAGS)
ENROLMENT = re.compile(
    r'(currently|must be|need to be|required to be|are) (enrolled|a (registered|current) student|'
    r'studying|pursuing a degree)|(p(a|å)g(a|å)ende|aktiva?) studier|inskriven (p(a|å) |vid )'
    r'|currently (pursuing|studying|enrolled|a (university )?student)'
    r'|(through )?pursuit of a (bachelor|master)|pursuing (a|an|your) (bachelor|master|degree|b\.?sc|m\.?sc)'
    r'|enrolled (in|at) (a |an )?(university|degree|bachelor|master|full[- ]time|study|programme|program)'
    r'|\buniversity student\b|\bpenultimate year\b|werkstudent|immatrikul|pflichtpraktikum'
    r'|praktikkurs|(analytical|curious|motivated|talented) students?\b(?! (or|and) (recent )?graduate)',
    FLAGS)
PAID = re.compile(
    r'\bpaid\b(?! (media|search|social|ads?|advertising|leave|parental|vacation|'
    r'holidays?|time off|sick))|\bsalary\b|\bstipend\b|remunerat|'
    r'ersättning utgår|ersattning utgar|betald praktik|praktiken är betald|'
    r'avlönad|\blön\b|månadslön|verg(ü|u)tung', FLAGS)
UNPAID = re.compile(
    r'\bunpaid\b|\bobetald|oavlönad|\bno (salary|compensation|remuneration|pay)\b|\bnot (be )?paid\b|'
    r'without (pay|salary|compensation)|ingen (lön|ersättning|ekonomisk ersättning)|'
    r'(betalar|utgår|utgar) inte[^.]{0,30}(lön|ersättning|ersattning)|\bej (lön|ersättning)', FLAGS)
NOT_UNPAID = re.compile(r"(don'?t|do not|never) (do|offer) unpaid|\bno unpaid\b", FLAGS)

RESEARCH = re.compile(r'\b(doktorand|doctoral|phd|ph\b.d|postdoc|postdoktor|'
                      r'forskare|forskarassistent|research fellow)', FLAGS)
GRADUATE = re.compile(r'\bgraduate\b|\bgrad\b|trainee|traineeship|traineeprogram|\btraineepro|'
                      r'early careers?|rotational|young professional|nyutexaminerad|'
                      r'absolvent|berufseinsteiger|starterspro', FLAGS)


def _rx(s):
    return re.compile(s, FLAGS) if s else None


class Screener(object):
    """Compiled rules for one candidate. Build it once per run."""

    def __init__(self, rules=None, profile=None):
        self.r = rules if rules is not None else load_rules()
        t = self.r.get('title', {})
        self.exclude = _rx(t.get('exclude'))
        self.include = _rx(t.get('include'))
        self.stems = _rx(t.get('include_stems'))
        self.family = _rx(t.get('family'))
        res = self.r.get('research', {})
        self.research_on = res.get('enabled', True)
        self.topics = _rx(res.get('topics'))
        self.method = _rx(res.get('method_words'))
        g = self.r.get('graduate_programmes', {})
        self.grad_on = g.get('enabled', True)
        self.grad_other = _rx(g.get('other_tracks'))
        c = self.r.get('content', {})
        self.signals = _rx(c.get('signals'))
        self.analytics = _rx(c.get('analytics_signals'))
        self.analytics_min = int(c.get('analytics_min', 0) or 0)
        lang = self.r.get('languages', {})
        self.blocked = [l.lower() for l in lang.get('cannot_work_in', [])]
        unknown = [l for l in self.blocked if l not in LANG_REQ]
        if unknown:
            raise SystemExit('screening.json: no patterns for language(s) %s. Known: %s'
                             % (', '.join(unknown), ', '.join(sorted(LANG_REQ))))
        self.knowledge_ok = set(l.lower() for l in lang.get('knowledge_is_enough', []))
        self.lang_req = {l: re.compile('(' + LANG_REQ[l] + ')', FLAGS) for l in self.blocked}
        self.lang_word = re.compile('|'.join(LANG_WORD[l] for l in self.blocked), FLAGS) if self.blocked else None
        self.max_years = int(self.r.get('years', {}).get('max_years_ok', 2))
        o = self.r.get('other', {})
        self.close_gig = o.get('close_gig_work', True)
        self.close_senior_prose = o.get('close_senior_prose', True)
        self.close_clearance = o.get('close_clearance_or_citizenship', True)
        self.intern = self.r.get('internships', {})
        self.profile = profile if profile is not None else {}

    # ------------------------------------------------------------- titles
    def is_graduate(self, t):
        return self.grad_on and bool(GRADUATE.search(t)) and not (self.grad_other and self.grad_other.search(t))

    def title_ok(self, t):
        t = t or ''
        if RESEARCH.search(t):
            if not self.research_on:
                return False
            return bool((self.topics and self.topics.search(t)) or (self.method and self.method.search(t)))
        if self.is_graduate(t):
            return True
        if self.exclude and self.exclude.search(t):
            return False
        return bool((self.include and self.include.search(t)) or (self.stems and self.stems.search(t)))

    def title_reason(self, t):
        if self.exclude and self.exclude.search(t or ''):
            return 'Title excluded (seniority or another profession)'
        return 'Title outside the target role families'

    # ------------------------------------------------------- work rights
    def authorization(self, country):
        """(has_right_to_work, needs_sponsorship) for a country name."""
        wa = (self.profile.get('work_authorization') or {})
        by = wa.get('by_country') or {}
        for name, v in by.items():
            if country and name.lower() == country.lower():
                return bool(v.get('right_to_work')), bool(v.get('needs_sponsorship'))
        d = wa.get('default') or {}
        return bool(d.get('right_to_work', False)), bool(d.get('needs_sponsorship', True))

    # ------------------------------------------------------------- body
    def language_block(self, text):
        """The first blocked language the ad requires, or None."""
        for lang, rx in self.lang_req.items():
            for m in rx.finditer(text):
                if _softened(text, m):
                    continue
                if lang in self.knowledge_ok:
                    sent = _sentence(text, m.start(), m.end())
                    if LANG_KNOW.search(sent) and not LANG_SPEAK.search(sent):
                        continue
                return lang
        if self.lang_word:
            for m in WORK_CLAUSE.finditer(text):
                c = m.group(0)
                w = self.lang_word.search(c)
                if w and not ENGLISH_WORD.search(c):
                    return w.group(0).lower()
        return None

    def internship_reason(self, text, title, authorized):
        if not (INTERN_EN.search(title or '') or INTERN_OTHER.search(title or '')):
            return None
        policy = self.intern.get('where_authorized' if authorized else 'where_sponsorship_needed',
                                 'conversion_or_paid')
        if policy == 'none':
            return 'Internship (internships are switched off in screening.json)'
        if self.intern.get('close_if_enrolment_required', True) and ENROLMENT.search(text):
            return 'Internship requiring current university enrolment'
        if policy == 'all':
            return None
        conv = bool(CONVERSION.search(text))
        paid = bool(PAID.search(text)) and not (UNPAID.search(text) and not NOT_UNPAID.search(text))
        if policy == 'conversion_only' and not conv:
            return 'Internship without a stated path to a permanent role'
        if policy == 'conversion_or_paid' and not (conv or paid):
            return 'Internship without a stated path to a permanent role and not stated as paid'
        return None

    def verdict(self, text, title, country=''):
        """None to keep, or the reason the ad is closed. Order matters: what the
        candidate cannot change comes first, so the recorded reason is the real
        blocker rather than a symptom."""
        authorized, needs_sponsor = self.authorization(country)
        lang = self.language_block(text)
        if lang:
            return 'Requires %s' % lang.capitalize()
        if needs_sponsor:
            m = NO_SPONSOR.search(text)
            if m and not self.sponsorship_offered_after(text, m.end()):
                return 'Rules out sponsorship or requires an existing right to work'
        if self.close_clearance:
            for m in CLEARANCE.finditer(text):
                if CLEARANCE_NOT.match(text[m.end():m.end() + 20]):
                    continue
                if not CONDITIONAL.search(_sentence(text, m.start(), m.end())):
                    return 'Security clearance or citizenship required'
        why = self.internship_reason(text, title, authorized and not needs_sponsor)
        if why:
            return why
        if self.signals and not self.signals.search(text) \
                and not (self.family and self.family.search(title or '')) \
                and not self.is_graduate(title or ''):
            an = set(m.group(0).lower() for m in self.analytics.finditer(text)) if self.analytics else set()
            if not self.analytics_min or len(an) < self.analytics_min:
                return 'No content from the target field in the description'
        bar = years_bar(text, floor=self.max_years + 1)
        if bar:
            return 'Years bar - %d+ years required' % bar
        if self.close_gig and GIG.search(text):
            return 'Hourly gig-platform or freelance-brokerage assignment, not employment'
        if self.close_senior_prose and SENIOR_PROSE.search(text):
            return 'Seniority stated in prose rather than in years - read before dismissing'
        return None

    @staticmethod
    def sponsorship_offered_after(text, end, window=400):
        seg = text[end:end + window]
        m = SPONSOR_OFFER.search(seg)
        if not m:
            return False
        return not SPONSOR_NEG_BEFORE.search(seg[max(0, m.start() - 80):m.start()])

    @staticmethod
    def sponsor_grade(text):
        """'visa', 'relocation' or 'silent'. A negated offer counts as silent."""
        for pat, grade in ((SPONSOR_VISA, 'visa'), (SPONSOR_RELO, 'relocation')):
            for m in pat.finditer(text):
                after = text[m.end():m.end() + 80]
                before = text[max(0, m.start() - 80):m.start()]
                if SPONSOR_NEG.match(after) or SPONSOR_NEG_BEFORE.search(before):
                    continue
                return grade
        return 'silent'

    @staticmethod
    def english_stated(text):
        return bool(ENGLISH_ONLY.search(text))
