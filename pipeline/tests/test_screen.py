# -*- coding: utf-8 -*-
"""Cases the screen must keep getting right. Run from the repo root:

    python -m unittest discover -s pipeline/tests -v

Each body is a shape seen in real ads. The suite guards against the mistakes
that keep coming back: a word boundary that compound words break, a
boilerplate sentence read as a requirement, a refusal read as an offer.
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from applypilot.screen import Screener, load_rules, years_bar  # noqa: E402

PROFILE = {'work_authorization': {
    'by_country': {'Sweden': {'right_to_work': True, 'needs_sponsorship': False}},
    'default': {'right_to_work': False, 'needs_sponsorship': True}}}
RULES = load_rules({'languages': {'knowledge_is_enough': ['swedish']}})
S = Screener(RULES, PROFILE)

ML = ('We work with machine learning on sensor data and build data pipelines '
      'in PyTorch. Time-series models in production. ')
BIZ = ('You will own our reporting: build dashboards in Tableau, define KPIs, run SQL '
       'against the warehouse, and turn the numbers into insight for the commercial team. ')


def v(text, title='Data Scientist', country='Sweden'):
    return S.verdict(text, title, country) or ''


class Titles(unittest.TestCase):
    KEEP = ['Data Engineer', 'Machine Learning Engineer', 'Applied AI Engineer', 'Dataanalytiker',
            'Datakonsult till expansivt techkonsultbolag!', 'Systemingenjör', 'Mjukvaruutvecklare',
            'Development Engineer',
            'Doctoral student in physics-guided foundation model for time-series data',
            'PhD student in machine learning for medical imaging',
            'Doktorandtjänst inom multimodal hjärnavbildning',
            'Postdoc in sensor fusion for condition monitoring',
            'Doctoral Researcher in Speech and Language Technology',
            'Machine Learning Intern', 'Praktikant inom dataanalys',
            'Graduate Talent Program', 'Technology Graduate Programme']
    DROP = ['Senior Data Engineer', 'Lead Machine Learning Engineer', 'Head of Data',
            'Data Engineering Manager', 'Säljare', 'Redovisningskonsult', 'Servicetekniker',
            'Talent Acquisition Partner', 'Examensarbete inom AI', 'Doktorand i kvantinformationsteori',
            'Postdoktor i ekologi', 'Graduate Nurse Programme', 'Sales Graduate Scheme']

    def test_keep(self):
        for t in self.KEEP:
            self.assertTrue(S.title_ok(t), t)

    def test_drop(self):
        for t in self.DROP:
            self.assertFalse(S.title_ok(t), t)


class Language(unittest.TestCase):
    def test_required(self):
        for s in ['Du pratar svenska.', 'Du kommunicerar väl på svenska.',
                  'Fluency in English is required, along with fluency in either Swedish or Norwegian.',
                  'The working language is Norwegian, Swedish or Danish.', 'Arbetsspråk är svenska.',
                  'Good communication skills in English and Swedish are required.',
                  'Förmåga att tala och skriva svenska obehindrat.',
                  'Du har goda kunskaper i svenska i tal och skrift.', 'You speak Swedish and English.',
                  'Mycket goda kunskaper i svenska (tal och skrift)',
                  'Sehr gute Deutschkenntnisse in Wort und Schrift.',
                  'Deutsch (C1) und Englisch', 'Uitstekende beheersing van de Nederlandse en Engelse taal',
                  'Norsk er arbeidsspråk.']:
            self.assertTrue(v(ML + s).startswith('Requires'), s)

    def test_not_required(self):
        for s in ['Working language is English; Swedish is not required.',
                  'Du har goda kunskaper i svenska och engelska.', 'Kunskaper i svenska är meriterande.',
                  'Knowledge of the Swedish language is required.', 'Good knowledge of Swedish and English',
                  'Fluent English. German language skills are a plus.',
                  'Our Danish customers are served from Copenhagen.', 'Nederlands is een pré.']:
            self.assertEqual(v(ML + s), '', s)


class RightToWork(unittest.TestCase):
    def test_refusal_closes_only_where_sponsorship_is_needed(self):
        t = ML + 'We are unable to offer visa sponsorship for this role.'
        self.assertEqual(v(t, country='Sweden'), '')
        self.assertIn('sponsorship', v(t, country='United Kingdom'))

    def test_refusal_shapes(self):
        for s in ["Visa Sponsorship: Can't currently sponsor",
                  'this role does not meet the criteria for visa sponsorship',
                  'You must already have the right to work in the UK.']:
            self.assertIn('sponsorship', v(ML + s, country='United Kingdom'), s)

    def test_offer_after_right_to_work_keeps(self):
        t = ML + ('Successful candidates must have the right to work in the UK. '
                  'We have a limited number of visa sponsorships available for this graduate role.')
        self.assertEqual(v(t, country='United Kingdom'), '')

    def test_sponsor_grade(self):
        self.assertEqual(S.sponsor_grade('We offer visa sponsorship and relocation support.'), 'visa')
        self.assertEqual(S.sponsor_grade('We are unable to offer visa sponsorship.'), 'silent')
        self.assertEqual(S.sponsor_grade('Relocation support is not provided for this position.'), 'silent')


class Clearance(unittest.TestCase):
    def test_closes(self):
        for s in ['This position requires a security clearance.', 'Swedish citizenship is required.',
                  'Krav: Svenskt medborgarskap.']:
            self.assertIn('clearance', v(ML + s), s)

    def test_conditional_or_negative_keeps(self):
        for s in ['Det kan förekomma att en anställning hos myndigheten är placerad i säkerhetsklass. '
                  'Om så är fallet görs en säkerhetsprövning.',
                  'Security clearance: No',
                  'Ta med pass och eventuellt bevis på uppehållstillstånd om du har ett medborgarskap utanför EU.',
                  'Observera att säkerhetsprövning kan bli aktuell för vissa tjänster.']:
            self.assertEqual(v(ML + s), '', s)


class Years(unittest.TestCase):
    def test_bars(self):
        for s, n in [('Mindestens drei Jahre relevante Praxiserfahrung.', 3), ('We require 5+ years of experience.', 5),
                     ('4-8 or more years in data engineering', 4), ('Vi söker dig med 5 eller fler års erfarenhet.', 5),
                     ('minimaal 3 jaar relevante ervaring', 3), ('3 - 4 (or more) years of work experience', 3), ('At least five years of experience in ML.', 5)]:
            self.assertEqual(years_bar(s, floor=3), n, s)

    def test_not_bars(self):
        for s in ['The team has grown a lot in the past two years.',
                  'The position is limited to four years, which extends to five years with teaching.',
                  'na 3 jaar dienstverband een sabbatical', '2 years of experience is a plus.']:
            self.assertIsNone(years_bar(s, floor=3), s)


class Content(unittest.TestCase):
    def test_gate(self):
        self.assertIn('No content', v('We are looking for a friendly barista for our cafe.', 'Barista'))
        self.assertEqual(v(BIZ, 'Commercial Analyst'), '')
        self.assertEqual(v('We sell insurance door to door.', 'Data Analyst'), '')  # family title rescues
        self.assertIn('gig', v(ML + 'Type: Hourly Contract. $20.00/hr - $100.00/hr.'))
        self.assertIn('Seniority', v(ML + 'You have extensive experience and mentor junior engineers.'))


class Internships(unittest.TestCase):
    def test_policy(self):
        self.assertEqual(v(ML, 'Machine Learning Intern', 'Sweden'), '')
        self.assertIn('enrolment', v(ML + 'You must be currently enrolled at a university.', 'Data Intern'))
        abroad = 'United Kingdom'
        self.assertIn('Internship', v(ML, 'Machine Learning Intern', abroad))
        self.assertEqual(v(ML + 'Successful interns receive a return offer.', 'Data Science Intern', abroad), '')
        self.assertEqual(v(ML + 'This is a 12-month paid internship.', 'AI Engineering Intern', abroad), '')
        self.assertIn('Internship', v(ML + 'Paid time off for staff. This is an unpaid internship.', 'Data Intern', abroad))
        self.assertEqual(v(ML, 'Systemingenjör till intern IT med fokus på AI'), '')


if __name__ == '__main__':
    unittest.main()
