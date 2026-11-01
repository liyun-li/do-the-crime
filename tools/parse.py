"""Pure parsing helpers: DOJ press release -> (months, one-liner) or None. Stdlib only."""
import re, html

NUM = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,
 'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,'seventeen':17,'eighteen':18,'nineteen':19,'twenty':20,'thirty':30,
 'forty':40,'fifty':50,'sixty':60,'seventy':70,'eighty':80,'ninety':90,'a':1,'an':1}
def num(s):
    s = s.lower().replace(',', '')
    try: return float(s)
    except ValueError: pass
    t = 0
    for p in re.split(r'[-\s]+', s):
        if p not in NUM: return None
        t += NUM[p]
    return t
NW = r'(?:\d+(?:\.\d+)?|(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[-\s](?:one|two|three|four|five|six|seven|eight|nine))?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|a|an)'
DUR = (r'(?P<dur>(?P<n1>' + NW + r')[-\s]+(?P<u1>years?|months?|days?)(?:’|\')?s?'
       r'(?:,?\s+and\s+(?P<n2>' + NW + r')[-\s]+(?P<u2>years?|months?|days?))?'
       r'(?:,?\s+and\s+(?P<n3>' + NW + r')[-\s]+(?P<u3>days?))?)')
PRISONISH = r'(?:in\s+(?:federal\s+)?prison|(?:of\s+)?imprisonment|(?:of\s+)?incarceration|in\s+(?:federal\s+)?custody|behind\s+bars|in\s+(?:a\s+)?federal\s+(?:prison|penitentiary|correctional)|prison\s+(?:term|sentence)|in\s+jail|of\s+prison)'
PROB = r'(?:of\s+)?(?:federal\s+)?probation'
LEAD = r'(?:sentenced|ordered)\b[^.;]{0,160}?\bto\s+(?:serve\s+)?(?:a\s+total\s+of\s+|a\s+combined\s+|an?\s+)?'
RX_PRISON = re.compile(LEAD + DUR + r'\s+' + PRISONISH, re.I)
RX_PROB = re.compile(LEAD + DUR + r'\s+' + PROB, re.I)
RX_TERM = re.compile(r'(?:sentenced|received|imposed|ordered)\b[^.;]{0,160}?\b(?:to\s+)?(?:a\s+(?:total\s+)?)?' + r'(?P<dur>(?P<n1>' + NW + r')[-\s](?P<u1>years?|months?))[-\s](?:federal\s+)?(?:prison\s+)?(?:sentence|term)', re.I)
RX_LIFE = re.compile(r'sentenced\b[^.;]{0,120}?\bto\s+(?:serve\s+)?(?:a\s+)?(?:mandatory\s+)?(?:(?:two|three|\d+)\s+(?:consecutive\s+)?)?life\b', re.I)
RX_TS = re.compile(r'time\s+served|home\s+(?:confinement|detention)|deferred|pretrial\s+diversion|community\s+confinement|halfway\s+house', re.I)
SENTENCE_WORD = re.compile(r'\bsentenced\b', re.I)

def months_of(m):
    t = 0.0
    for n, u in (('n1','u1'),('n2','u2'),('n3','u3')):
        try: nn, uu = m.group(n), m.group(u)
        except IndexError: continue
        if not nn: continue
        v = num(nn)
        if v is None: return None
        uu = uu.lower()
        t += v * 12 if uu.startswith('year') else v if uu.startswith('month') else v / 30.4
    return round(t, 1)

def clean_html(s):
    s = re.sub(r'<(br|/p|/li|/h\d)[^>]*>', '\n', s or '', flags=re.I)
    s = re.sub(r'<[^>]+>', ' ', s); s = html.unescape(s).replace('\xa0', ' ')
    s = re.sub(r'[ \t]+', ' ', s)
    return [p.strip() for p in s.split('\n') if p.strip()]

def sentence_months(title, paras):
    """Return (months, kind) where kind in prison/probation/life, or (None, reason)."""
    body = ' '.join(paras[:5])
    tb = title + '. ' + body
    if RX_LIFE.search(tb):
        return 9999, 'life'
    vals = set(); kinds = set()
    for rx, kind in ((RX_PRISON, 'prison'), (RX_TERM, 'prison'), (RX_PROB, 'probation')):
        for m in rx.finditer(body):
            v = months_of(m)
            if v is None: continue
            vals.add(0.0 if kind == 'probation' else v); kinds.add(kind)
    if not vals: return None, 'no-duration'
    if 'prison' in kinds and 'probation' in kinds: vals.discard(0.0)
    if len(vals) > 1: return None, 'multiple:%s' % sorted(vals)
    v = vals.pop()
    if v == 0.0 and RX_TS.search(body[:1500]): return None, 'time-served'
    # title sanity: an exact number in the title must agree
    mt = re.search(r'sentenced\s+to\s+(?:a\s+total\s+of\s+|combined\s+)?' + DUR, title, re.I)
    if mt and not re.search(r'(more than|over|nearly|almost|about|approximately|at least|up to|combined|total)\s*$', title[:mt.start('dur')], re.I):
        tv = months_of(mt)
        if tv is not None and abs(tv - v) > 0.6: return None, 'title-mismatch %s vs %s' % (tv, v)
    mo = re.search(r'(more than|over|nearly|almost|about|approximately|at least)\s+' + DUR, title, re.I)
    if mo:
        tv = months_of(mo)
        if tv is not None:
            lo, hi = (tv, tv + 12 if tv >= 24 else tv * 1.5) if mo.group(1).lower() in ('more than', 'over', 'at least') else (tv * 0.85, tv * 1.15 + 1)
            if not (lo <= v <= hi): return None, 'title-mismatch %s vs %s' % (tv, v)
    if re.search(r'consecutive', body[:2500], re.I) and not re.search(r'total|combined', body[:2500], re.I):
        return None, 'consecutive'
    if v != 0.0 and v < 1: return None, 'days-only'
    return v, ('probation' if v == 0.0 else 'prison')

# ---------- exclusions (title + crime phrase: strict) ----------
EXCL = re.compile(r'\b(sex\w*|child\w*|minors?|juvenile|teen\w*|pornograph\w*|csam|obscen\w*|rap(e|ed|ist)|incest|molest\w*|enticement|groom\w*|'
 r'murder\w*|homicide|manslaughter|kill\w*|slay\w*|slain|death|deaths|dead|died|dies|fatal\w*|corpse|remains|body of|bodies|'
 r'kidnap\w*|hostage|tortur\w*|carjack\w*|stabb\w*|shoot\w*|shot|gunfire|maim\w*|mutilat\w*|dismember\w*|bloody|gore|'
 r'human\s+(?:trafficking|smuggling)|sex\s+trafficking|forced\s+labor|prostitut\w*|exploitation|abus\w*|domestic\s+violence|stalk\w*|'
 r'expos(?:ing|ed)\s+(?:him|her)sel\w*|indecen\w*|lewd\w*|voyeur\w*|animal\s+crush\w*|cruelty|puppy|dog\s*fight\w*|cockfight\w*|suicide|overdose|terroris\w*|isis|al[\s-]qaeda|hate\s+crime|'
 r'illegal(?:ly)?\s+re-?ent\w*|reentry|re-entry|alien\w*|illegally\s+present|deport\w*|immigra\w*|unlawfully\s+present)\b', re.I)
MULTI = re.compile(r'\b(two|three|four|five|six|seven|eight|nine|ten|\d+|several|multiple|final|last|all)\s+(?:\S+\s+){0,3}?(men|women|people|persons|defendants|individuals|members|brothers|sisters|siblings|associates|co-?defendants|co-?conspirators|fraudsters|leaders|operators|owners|executives|officers|nationals|residents|others|more|dealers|traffickers|felons|employees)\b|'
 r'\b(couple|brothers|sisters|duo|trio|husband and wife|father and son|mother and|defendants|co-?defendants|ring|gang members|respectively|each sentenced|are sentenced|were sentenced)\b', re.I)
NATION = re.compile(r'\b(unlawfully in the (?:country|united states)|in the country illegally|national|citizen|alien|illegal|undocumented|immigrant|refugee|asylum|foreign[- ]born|'
 r'belarusian|moldovan|latvian|lithuanian|estonian|kazakh|uzbek|sri lankan|bangladeshi|nepali|burmese|mongolian|singaporean|dutch|swiss|swedish|norwegian|danish|finnish|greek|portuguese|austrian|belgian|hungarian|czech|slovak|croatian|bosnian|macedonian|kosovar|moroccan|algerian|tunisian|libyan|jordanian|yemeni|qatari|kuwaiti|palestinian|senegalese|malian|ivorian|togolese|gambian|guinean|zambian|zimbabwean|ugandan|tanzanian|rwandan|angolan|mexican|honduran|guatemalan|salvadoran|dominican|chinese|russian|nigerian|ghanaian|cuban|venezuelan|colombian|haitian|jamaican|indian|pakistani|iranian|korean|vietnamese|filipino|canadian|british|israeli|ukrainian|romanian|brazilian|peruvian|ecuadorian|nicaraguan|turkish|syrian|iraqi|afghan|somali|kenyan|egyptian|lebanese|saudi|emirati|albanian|armenian|georgian|bulgarian|serbian|polish|german|french|italian|spanish|irish|japanese|taiwanese|thai|cambodian|laotian|indonesian|malaysian|australian|south african|ethiopian|eritrean|sudanese|liberian|cameroonian|congolese|chilean|argentine|bolivian|uruguayan|paraguayan|panamanian|costa rican|belizean|bahamian|trinidadian|guyanese|barbadian)\b', re.I)
# body: same idea, minus words that are routine boilerplate in DOJ prose ("Immigration and Customs Enforcement", "case remains")
EXCL_BODY = re.compile(r'\b(sex\w*|child\w*|minors?|juvenile|pornograph\w*|csam|obscen\w*|rap(e|ed|ist)|incest|molest\w*|enticement|'
 r'murder\w*|homicide|manslaughter|kill\w*|slay\w*|slain|death|deaths|died|fatal\w*|corpse|'
 r'kidnap\w*|hostage|tortur\w*|carjack\w*|stabb\w*|shoot\w*|shot|gunfire|maim\w*|mutilat\w*|dismember\w*|'
 r'human\s+(?:trafficking|smuggling)|sex\s+trafficking|forced\s+labor|prostitut\w*|domestic\s+violence|stalk\w*|'
 r'expos(?:ing|ed)\s+(?:him|her)sel\w*|indecen\w*|lewd\w*|voyeur\w*|animal\s+crush\w*|cruelty|dog\s*fight\w*|cockfight\w*|suicide|overdose|terroris\w*|isis|hate\s+crime|'
 r'illegal(?:ly)?\s+re-?ent\w*|reentry|re-entry|illegal\s+aliens?|aliens?\s+in\s+possession|deported|removed\s+from\s+the\s+united)\b', re.I)
# partner violence, hate-motivated, serious injury, places of worship (checked on title + lead paragraphs)
EXCL2 = re.compile(r'\b(romantic\s+partner|intimate\s+partner|girl\s?friends?|boy\s?friends?|spouse|ex-wife|ex-husband|pregnant|strangl\w*|chok(?:e|ed|ing)|'
 r'antisemit\w*|anti-semit\w*|racis\w*|racially|swastika|noose|bodily\s+injur\w*|domestic\s+(?:assault|violence|abuse)|abduct\w*|cyberstalk\w*|'
 r'on\s+fire|metal\s+rod|church|mosque|synagogue|temple|disfigur\w*|bludgeon\w*|beat(?:ing)?\s+(?:a|the|his|her)\b)', re.I)
IDENT = re.compile(r'\b(gay|lesbian|transgender|muslim|jewish|christian|catholic|hindu|sikh|buddhist|black|white|hispanic|latino|latina|asian|native american|tribal|tribe|indian country|reservation|pueblo|disab\w*|blind|deaf|wheelchair)\b', re.I)

def name_tokens(paras):
    """Collect likely person-name tokens from the body ('First Last, 45, of ...', 'sentenced First Last')."""
    toks = set(); body = ' '.join(paras[:8])
    for m in re.finditer(r"((?:[A-Z][A-Za-z'’\-]+|[A-Z]\.)(?:\s+(?:[A-Z][A-Za-z'’\-]+|[A-Z]\.|Jr\.?|Sr\.?|III|II|IV|de|del|la|van|von))+)\s*,\s*(?:a/k/a[^,]*,\s*)?(?:aged?\s+|age\s+)?\d{2}\b", body):
        toks.update(t for t in re.split(r'[\s\-]+', m.group(1)) if len(t) > 2 and t[0].isupper())
    for m in re.finditer(r"(?:sentenced|Judge|Attorney|Agent|Chief|announced that|v\.)\s+((?:[A-Z][A-Za-z'’\-]+\s+){1,3}[A-Z][A-Za-z'’\-]+)", body):
        toks.update(t for t in re.split(r'[\s\-]+', m.group(1)) if len(t) > 2)
    # surnames repeated alone later in the release ("Moultrie pleaded guilty")
    for m in re.finditer(r"(?<=[.;] )([A-Z][a-z'’\-]{2,})\s+(?:pleaded|was|admitted|is|had|used|submitted|obtained|also|and)\b", body):
        toks.add(m.group(1))
    return toks - {'The','United','States','District','Court','Attorney','Office','Department','Justice','Federal','Judge','Chief','Senior','Acting','Special','Agent','According','After','During','Today','Assistant','General','Northern','Southern','Eastern','Western','Middle','Central','County','City','Police','Bureau','Investigation','Homeland','Security','Investigations','Service','Internal','Revenue','Criminal','Division','Drug','Enforcement','Administration','Postal','Inspection','Secret','Marshals','Immigration','Customs','Office','Inspector','His','Her','Their','This','That','These','Those','From','Following','Under','Between','When','While','Since','Also','Evidence','Court','Documents','Records'}

VOCAB = set()
PLACEWORDS = {'County','Parish','City','Island','Beach','Falls','Springs','Valley','Lake','Park','Heights','Township','Borough','Village','Mountain','Bay','Harbor','Creek','Point','Station','Day','Street','Avenue','Road','Beach','Hills','River','Rock','Grove','Bend','Gary','Mobile','Independence','Liberty','Union','Commerce','Reading','Ocean','Coast','Valley','North','South','East','West','New','Fort','Port','Mount','Saint','Grand','Little','Big','Long','Lake'}
def caser(phrase, subject=False):
    """Title Case -> sentence case using a vocabulary of words seen in lowercase in DOJ prose."""
    out = []; ws = phrase.split(); role_at = len(ws)
    if subject:
        for i, w in enumerate(ws):
            ww = re.sub(r'\W', '', w)
            if SUBJ_KEEP.fullmatch(ww) and ww.lower() not in ('former', 'ex'): role_at = i; break
    for i, w in enumerate(ws):
        core = re.sub(r'^[^\w$]+|[^\w%]+$', '', w)
        prev_cap = i > 0 and ws[i-1][:1].isupper() and (re.sub(r'\W', '', ws[i-1]).lower() not in VOCAB or ws[i-1].endswith('.'))
        if subject and i < role_at: out.append(w if re.sub(r'\W', '', w).lower() not in ('former', 'ex') else w.lower()); continue
        if core in PLACEWORDS and (prev_cap or (i + 1 < len(ws) and ws[i+1][:1].isupper() and re.sub(r'\W', '', ws[i+1]).lower() not in VOCAB)): out.append(w); continue
        if core in KEEPCAP or (core in STATES_KEEP): out.append(w); continue
        if core and inv(core) and not (core.isupper() and len(core) > 1 and core.lower() not in ('a','i')) and core[0].isupper():
            w = w.replace(core, core.lower(), 1)
        out.append(w)
    s = ' '.join(out)
    return re.sub(r'(?<=\w )A(?= [a-z])', 'a', s)

SUBJ_KEEP = re.compile(r'\b(man|woman|resident|owner|former|ex|ceo|cfo|executive|doctor|physician|nurse|pharmacist|dentist|chiropractor|lawyer|attorney|accountant|cpa|officer|deputy|guard|employee|worker|manager|director|president|founder|operator|dealer|felon|driver|trucker|pilot|captain|fisherman|hunter|guide|farmer|rancher|contractor|businessman|businesswoman|preparer|broker|adviser|advisor|investor|promoter|rapper|influencer|teacher|coach|official|clerk|mayor|councilman|councilwoman|commissioner|sheriff|trooper|agent|soldier|sergeant|veteran|marine|sailor|smuggler|hacker|programmer|engineer|scientist|professor|student|pastor|priest|banker|teller|landlord|realtor|chef|cook|bartender|mechanic|electrician|plumber|carrier|postal|letter|mail|inmate|prisoner|fugitive|leader|boss|member|associate|kingpin|supplier|courier|mule|trafficker|counterfeiter|fraudster|scammer|thief|robber|burglar|arsonist|poacher|collector|seller|vendor|shopkeeper|landscaper|roofer|builder|developer|consultant|therapist|counselor|technician|administrator|assistant|aide|secretary|treasurer|bookkeeper|controller|lobbyist|politician|legislator|senator|representative|judge|tycoon|mogul|heir|socialite|celebrity|athlete|player|boxer|wrestler)\b', re.I)

def split_title(title):
    t = re.sub(r'\s+', ' ', html.unescape(title)).strip().rstrip('.')
    if sum(ch.isupper() for ch in t) > 0.6 * sum(ch.isalpha() for ch in t): t = t.title().replace("’S ", "’s ").replace("'S ", "'s ")
    m = re.search(r'\s+(?:Is\s+|Was\s+|Gets\s+)?Sentenced\b', t, re.I)
    if not m: return None, None
    subj, rest = t[:m.start()].strip(), t[m.end():].strip()
    rest = re.sub(r'^(?:in\s+(?:[A-Z][\w.]*\s+){0,2}(?:federal\s+|district\s+)?court\s+)?to\s+(?:serve\s+)?(?:more\s+than\s+|over\s+|nearly\s+|almost\s+|about\s+|a\s+total\s+of\s+|combined\s+)?(?:\S+[-\s]+(?:years?|months?|days?)(?:’|\')?s?(?:\s+and\s+\S+[-\s]+(?:months?|days?|years?))?|life|probation|time served)(?:\s+(?:in|of)\s+(?:federal\s+)?(?:prison|imprisonment|probation|custody|jail))?\s*', '', rest, flags=re.I)
    rest = re.sub(r'^(?:to\s+)?(?:federal\s+)?(?:prison|imprisonment|probation)\s*', '', rest, flags=re.I)
    rest = re.sub(r'^,\s*', '', rest)
    m2 = re.match(r'^(?:for|after|in\s+connection\s+with|in|on|over|following)\s+(.*)$', rest, re.I)
    crime = m2.group(1) if m2 else ''
    crime = re.sub(r'^(?:his|her|their|the)\s+role\s+in\s+(?:an?\s+|the\s+)?', '', crime, flags=re.I)
    crime = re.sub(r'^(?:pleading\s+guilty|being\s+convicted|conviction)\s+(?:in|to|of|for)\s+(?:an?\s+|the\s+)?', '', crime, flags=re.I)
    crime = re.sub(r'^(?:role\s+in\s+)(?:an?\s+|the\s+)?', '', crime, flags=re.I)
    crime = re.sub(r'^(?:federal|a|an|the)\s+', lambda x: '' if x.group(0).lower().strip() in ('a','an','the') else x.group(0), crime, flags=re.I)
    return subj, crime

def crime_from_body(paras):
    body = ' '.join(paras[:3])
    T = r'((?:[^.;,]|\.(?=\d)|,(?=\d{3}))' + '{8,140}?)'
    for rx in (r'sentenced\b[^.]{0,200}?\bfor\s+(?:his|her|their)\s+role\s+in\s+(?:an?\s+|the\s+)?' + T + r'(?:,(?!\d)|\.(?!\d)|;|\s+announced|\s+U\.S\.)',
               r'sentenced\b[^.]{0,200}?\b(?:imprisonment|prison|probation)\s+(?:for|after\s+pleading\s+guilty\s+to|after\s+being\s+convicted\s+of)\s+' + T + r'(?:,(?!\d)|\.(?!\d)|;|\s+announced|\s+U\.S\.)',
               r'pleaded\s+guilty\s+(?:in\s+\w+\s+\d{4}\s+)?to\s+' + T + r'(?:,(?!\d)|\.(?!\d)|;)',
               r'convicted\s+(?:at\s+trial\s+)?of\s+' + T + r'(?:,(?!\d)|\.(?!\d)|;)'):
        m = re.search(rx, body, re.I)
        if m: return m.group(1)
    return ''

PLACES = set()
KEEPCAP = {'St','St.','I','U.S.','Ponzi','Medicare','Medicaid','Internet','COVID','COVID-19','IRS','FBI','DEA','ATF','SNAP','PPP','EIDL','NFL','NBA','MLB','Navy','Army','Air','Force','Marine','Corps','Coast','Guard','Postal','Service','Social','Security','Bible','Super','Bowl','Amazon','Apple','Google','Facebook','Instagram','Bitcoin','Ethereum','Christmas','Halloween','Thanksgiving','Day','Valentine’s',"Valentine's",'Easter','Olympic','Olympics','Pentagon','Capitol','White','House','Congress','Senate','Treasury','Veterans','Affairs','Disney','Walmart','Rolex'}
STATES_KEEP = set('Alabama Alaska Arizona Arkansas California Colorado Connecticut Delaware Florida Georgia Hawaii Idaho Illinois Indiana Iowa Kansas Kentucky Louisiana Maine Maryland Massachusetts Michigan Minnesota Mississippi Missouri Montana Nebraska Nevada Ohio Oklahoma Oregon Pennsylvania Tennessee Texas Utah Vermont Virginia Washington Wisconsin Wyoming Carolina Dakota Jersey Hampshire Mexico York Rhode Puerto Rico Guam America American United States China Russia Iran Hong Kong Germany Canada Japan'.split())
def inv(w):
    l = w.lower()
    return l in VOCAB or (l.endswith('s') and l[:-1] in VOCAB) or (l.endswith('es') and l[:-2] in VOCAB) or (l.endswith('ies') and l[:-3] + 'y' in VOCAB)
STATES = set('Alabama Alaska Arizona Arkansas California Colorado Connecticut Delaware Florida Georgia Hawaii Idaho Illinois Indiana Iowa Kansas Kentucky Louisiana Maine Maryland Massachusetts Michigan Minnesota Mississippi Missouri Montana Nebraska Nevada Ohio Oklahoma Oregon Pennsylvania Tennessee Texas Utah Vermont Virginia Washington Wisconsin Wyoming Carolina Dakota Jersey Hampshire Mexico York Rhode Island Puerto Rico Guam America American U.S. US USA United States'.split())
def harvest_places(paras):
    body = ' '.join(paras[:6])
    for m in re.finditer(r"\b(?:of|in|near|from)\s+((?:[A-Z][A-Za-z.'’\-]+\s+){0,2}[A-Z][A-Za-z.'’\-]+),\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", body):
        if m.group(2).split()[-1] in STATES_KEEP: PLACES.update(m.group(1).split())
    m = re.match(r"\s*((?:[A-Z][A-Za-z.'’\-]+[\s,]+){0,4})", paras[0] if paras else '')
    if m: PLACES.update(w.strip(',') for w in m.group(1).split())
HONORIFIC = re.compile(r"\b(Representative|Rep\.|Senator|Sen\.|Congress(?:man|woman)|Governor|Gov\.|Mayor|Judge|Officer|Deputy|Trooper|Agent|Detective|Sheriff|Mr\.|Mrs\.|Ms\.|Dr\.|President)\s+[A-Z][a-z]", re.I)
def person_like(crime):
    """True if the (already sentence-cased) crime phrase seems to contain a person's name."""
    if HONORIFIC.search(crime): return True
    toks = re.findall(r"[A-Za-z][A-Za-z'’\-]*", crime)
    run = 0
    for i, w in enumerate(toks):
        cap = w[0].isupper() and not w.isupper() and not inv(w) and w not in KEEPCAP and w not in PLACES and w not in STATES and i > 0
        run = run + 1 if cap else 0
        if run >= 2: return True
    return False
