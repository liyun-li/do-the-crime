#!/usr/bin/env python3
"""Do The Crime data builder. Clients never call justice.gov: this runs once a day in GitHub Actions
(or locally with --from DIR) and writes tools/review_queue.json.  Stdlib only.

The game itself plays only the hand-curated, hand-verified curated.json.  New auto-parsed
releases land in the review queue for a human to check (sentence, wording, exclusions) and
promote by hand via curate/picks.tsv; nothing auto-parsed goes straight into play."""
import json, os, re, sys, time, glob, datetime, urllib.request, collections
sys.path.insert(0, os.path.dirname(__file__))
import parse as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'review_queue.json'); CUR = os.path.join(ROOT, 'curated.json'); ZH = os.path.join(ROOT, 'tools', 'zh.json'); VOC = os.path.join(ROOT, 'tools', 'vocab.txt')
UA = 'DoTheCrimeGame/1.0 (+https://github.com/liyun-li/do-the-crime; once-daily cached fetch)'
API = 'https://www.justice.gov/api/v1/press_releases.json?pagesize=50&page=%d&sort=date&direction=DESC&parameters%%5Btitle%%5D=sentenced'
MAX_REQ = int(os.environ.get('DTC_MAX_REQ', '12'))   # hard cap per refresh
POOL_MAX = 4000
REQ = 0

def get(url):
    global REQ
    for k in range(4):
        if REQ >= MAX_REQ: return None
        REQ += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'}), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print('retry', k, e, file=sys.stderr); time.sleep(5 * 2 ** k)
    return None

CATS = [('wildlife', r'wildlife|eagle|bald|turtle|manatee|alligator|fish(?:ing)?\b|shark|elephant|ivory|rhino|bird|parrot|owl|hawk|falcon|lacey act|poach|deer|elk|bear|whale|dolphin|coral|endangered|migratory|reptile|snake|tiger|monkey|primate|feather|pelican|antler|bighorn'),
        ('crypto', r'crypto|bitcoin|ether|nft|blockchain|token|mining rig|wallet'),
        ('cyber', r'hack|computer|ransom|malware|botnet|phish|cyber|sim swap|ddos|dark ?web|data breach|intrusion'),
        ('tax', r'\btax|irs\b|payroll|return preparer|employment taxes'),
        ('covid', r'covid|pandemic|ppp\b|paycheck protection|eidl|unemployment insurance|stimulus'),
        ('health', r'health ?care|medicare|medicaid|tricare|pharmac|prescription|clinic|doctor|physician|nurse|opioid pill|pill mill|durable medical|telemedicine|genetic test|hospice|ambulance'),
        ('mail', r'postal|mail theft|stealing mail|mail carrier|letter carrier|post office|usps|arrow key'),
        ('corruption', r'brib|kickback|extort|corrupt|public official|embezzl|honest services|bid[- ]rigging|price[- ]fixing|obstruct|perjur|false statement|lying|lied'),
        ('fraud', r'fraud|scheme|scam|ponzi|launder|counterfeit|forg|identity theft|stolen identit|check|wire|bank|loan|mortgage|investment|securities|insider|embezzl|theft of government|social security|benefits|snap|food stamp|grant'),
        ('theft', r'theft|stole|steal|burglar|robber|shoplift|stolen|larceny|heist|catalytic|truck|cargo|atm'),
        ('threat', r'threat|threaten|swat|bomb hoax|hoax|harass'),
        ('firearm', r'firearm|gun|pistol|rifle|ammunition|machine ?gun|silencer|suppressor|switch|explosive|pipe bomb|grenade|armed'),
        ('drugs', r'drug|cocaine|meth|fentanyl|heroin|marijuana|cannabis|oxycodone|narcotic|controlled substance|pills|crack|kilogram|pounds of'),
        ('violent', r'assault|robbery|attack|carjack|arson|riot|violent|beat|punch|struck|injur|hit')]
VIOLENTISH = {'firearm', 'drugs', 'violent', 'threat', 'theft'}
SOFT = {'fraud', 'tax', 'covid', 'health', 'corruption', 'crypto', 'cyber', 'wildlife', 'mail'}

def category(s, topics):
    s = re.sub(r'\b(eagle (?:pass|butte|county|river)|turtle (?:creek|mountain)|coral (?:springs|gables)|bear (?:creek|river))\b', ' ', s.lower())
    for c, rx in CATS:
        if re.search(r'\b(?:' + rx + r')', s): return c
    t = re.sub(r'\b(eagle (?:pass|butte)|turtle creek|coral springs)\b', ' ', ' '.join(topics).lower())
    for c, rx in CATS:
        if re.search(r'\b(?:' + rx + r')', t): return c
    return 'other'

def state_of(r):
    for c in r.get('component') or []:
        m = re.match(r'USAO - ([^,]+)', c.get('name', ''))
        if m: return m.group(1).strip()
    return ''

def build_one(r, stats):
    title = P.html.unescape(r.get('title') or '')
    if not P.SENTENCE_WORD.search(title): stats['no-sentenced'] += 1; return None
    paras = P.clean_html(r.get('body'))
    if P.EXCL.search(title) or P.EXCL_BODY.search(' '.join(paras[:6])) or P.EXCL2.search(title+' '+' '.join(paras[:3])): stats['excluded-topic'] += 1; return None
    if P.MULTI.search(title) or P.MULTI.search(' '.join(paras[:2])): stats['multi-defendant'] += 1; return None
    subj, crime = P.split_title(title)
    if subj is None: stats['no-split'] += 1; return None
    sw = subj.split()
    if sw and re.search(r'(?<![su])s$', sw[-1]) and sw[-1].lower() not in ('boss', 'business', 'witness', 'actress', 'hostess', 'waitress', 'heiress', 'mistress', 'prince ss'):
        stats['plural-subject'] += 1; return None
    months, kind = P.sentence_months(title, paras)
    if months is None: stats['sentence:' + kind.split(' ')[0].split(':')[0]] += 1; return None
    names = P.name_tokens(paras)
    if not crime: crime = P.crime_from_body(paras); stats['crime-from-body'] += 1 if crime else 0
    crime = re.sub(r'\s+', ' ', crime).strip(' .,;:')
    crime = re.sub(r'\s+(?:announced|U\.S\. Attorney).*$', '', crime)
    crime = re.split(r'\s*;\s*|\s+[-–—]\s+(?=[a-z])', crime)[0]
    if re.search(r'\b(years?|months?|prison|sentence[ds]?|probation|life|incarcerat\w*)\b', crime, re.I): stats['spoiler'] += 1; return None
    if not crime or len(crime) < 8: stats['no-crime'] += 1; return None
    if re.fullmatch(r'(?:federal\s+|illegal(?:ly)?\s+|unlawful(?:ly)?\s+)?(?:possessing\s+|possession\s+of\s+)?(?:an?\s+)?(?:firearms?|guns?|drugs?|weapons?|narcotics?|ammunition)(?:\s+(?:and|&)\s+(?:firearms?|guns?|drugs?|weapons?|narcotics?|ammunition))?(?:\s+(?:charges?|offenses?|violations?|crimes?|counts?))?', crime, re.I):
        stats['too-generic'] += 1; return None
    if len(crime) > 120: stats['crime-too-long'] += 1; return None
    toks = set(re.findall(r"[A-Za-z][A-Za-z'’\-]+", crime))
    if toks & names: stats['name-in-crime'] += 1; return None
    if P.person_like(P.caser(crime[0].upper() + crime[1:])): stats['person-like-crime'] += 1; return None
    if P.NATION.search(crime) or P.IDENT.search(crime): stats['identity-in-crime'] += 1; return None
    if re.search(r'\b(vs?\.|united states v)\b', crime, re.I): stats['caption'] += 1; return None
    if (set(re.findall(r"[A-Za-z][A-Za-z'’\-]+", subj)) & names) or P.NATION.search(subj) or P.IDENT.search(subj) or not P.SUBJ_KEEP.search(subj):
        subj = ''
    subj = re.sub(r'^(?:a|an|the)\s+', '', subj, flags=re.I)
    if re.search(r'\b(charged|fined|apprehended|plead\w*|and|who)\s*$|\bcharged with\b|,\s*$', subj, re.I): subj = ''
    d = datetime.datetime.fromtimestamp(int(r.get('date') or 0), datetime.timezone.utc)
    topics = [t.get('name', '') for t in (r.get('topic') or [])]
    cat = category(crime, topics)
    crime = re.sub(r'(?<=[a-z])-(Based|Linked|Related|Owned|Run|Funded|Backed)\b', lambda m: '-' + m.group(1).lower(), crime)
    return {'id': r['uuid'][:12], 'm': months, 'k': kind, 's': P.caser(subj, True), 'c': P.caser(crime[0].upper() + crime[1:]),
            'g': cat, 'y': d.year, 'st': state_of(r), 'u': r['url']}

def main():
    stats = collections.Counter()
    prev = json.load(open(OUT)) if os.path.exists(OUT) else {'cases': []}
    old = {c['id']: c for c in prev.get('cases', [])}
    P.VOCAB.update(open(VOC).read().split()) if os.path.exists(VOC) else None
    SF = os.path.join(ROOT, 'tools', 'seen.txt')
    global SEEN
    SEEN = set(open(SF).read().split()) if os.path.exists(SF) else set()
    items = []
    if '--from' in sys.argv:
        for d in sys.argv[sys.argv.index('--from') + 1].split(','):
            for f in sorted(glob.glob(os.path.join(d, 'p*.json')), key=lambda x: int(re.findall(r'\d+', os.path.basename(x))[0])):
                items += json.load(open(f))['results']
        seen_u = set(); items = [r for r in items if not (r.get('url') in seen_u or seen_u.add(r.get('url')))]
    else:
        known = set(old) | SEEN
        for p in range(MAX_REQ):
            d = get(API % p)
            if not d: break
            res = d.get('results') or []
            items += res
            # stop once a whole page is already known (releases arrive newest first)
            if not res or all((r.get('uuid') or '')[:12] in known for r in res): break
            time.sleep(2)
        if not items:
            print('API unreachable; keeping previous review queue (requests=%d)' % REQ); return 0
    if not P.VOCAB:
        cnt = collections.Counter()
        for r in items:
            for w in re.findall(r'(?<![.!?]\s)(?<=\s)([a-z][a-z\-]{1,})\b', ' '.join(P.clean_html(r.get('body')))): cnt[w] += 1
        P.VOCAB.update(w for w, n in cnt.items() if n >= 2)
        open(VOC, 'w').write('\n'.join(sorted(P.VOCAB)))
    PL = os.path.join(ROOT, 'tools', 'places.txt')
    if os.path.exists(PL): P.PLACES.update(l for l in open(PL).read().splitlines() if l.strip())
    for r in items: P.harvest_places(P.clean_html(r.get('body')))
    open(PL, 'w').write('\n'.join(sorted(P.PLACES)))
    zh = json.load(open(ZH)) if os.path.exists(ZH) else {}
    new = {}; dupe = {(c['c'].lower(), c['m']): c['id'] for c in old.values()}
    for r in items:
        if not r.get('uuid'): continue
        c = build_one(r, stats)
        if not c: continue
        key = (c['c'].lower(), c['m'])
        if dupe.get(key, c['id']) != c['id']: stats['duplicate'] += 1; continue
        dupe[key] = c['id']; new[c['id']] = c; stats['kept'] += 1
    today = datetime.date.today().isoformat()
    DROP = set(open(os.path.join(ROOT,'tools','drop.txt')).read().split()) if os.path.exists(os.path.join(ROOT,'tools','drop.txt')) else set()
    CURATED = {c['id'] for c in json.load(open(CUR))['cases']} if os.path.exists(CUR) else set()
    DROP |= CURATED   # already promoted: no need to review again
    merged = {k: v for k, v in old.items() if k not in DROP}
    for k, c in new.items():
        if k in DROP: stats['hand-dropped'] += 1; continue
        c['a'] = old[k]['a'] if k in old else ('2026-10-31' if '--from' in sys.argv else today)
        merged[k] = c
    for k, c in merged.items():
        if k in zh: c['zs'], c['zc'] = zh[k].get('s', ''), zh[k]['c']
        else: c.pop('zs', None); c.pop('zc', None)
    cases = sorted(merged.values(), key=lambda c: (c['a'], c['id']), reverse=True)[:POOL_MAX]
    cases.sort(key=lambda c: c['id'])
    mix = collections.Counter(c['g'] for c in cases)
    out = {'note': 'REVIEW QUEUE - not played. Verify against the DOJ link before promoting via curate/picks.tsv.',
           'n': len(cases), 'mix': dict(sorted(mix.items())), 'cases': cases}
    print('stats', dict(stats))
    print('pool', len(cases), 'new', len(set(new) - set(old)), 'mix', dict(mix))
    if '--dry' in sys.argv: return 0
    order = [(r.get('uuid') or '')[:12] for r in items if r.get('uuid')]
    allseen = list(dict.fromkeys(order + sorted(SEEN - set(order))))[:8000]
    open(SF, 'w').write('\n'.join(sorted(allseen)) + '\n')
    if json.dumps({k: v for k, v in prev.items() if k != 'updated'}, sort_keys=True) == json.dumps(out, sort_keys=True):
        print('no change; requests this refresh: %d' % REQ); return 0
    out = {'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), **out}
    with open(OUT, 'w') as f: json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print('requests this refresh: %d' % REQ)
    return 0

if __name__ == '__main__': sys.exit(main())
