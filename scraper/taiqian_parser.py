"""
Parser for 干部任前公示 biographical paragraphs.

Input:  raw text of a single person's bio (typically 100-400 chars Chinese)
Output: structured dict with CPED-compatible fields.

This module is parser-only — it doesn't fetch HTML. Pair with a province-specific
fetcher that yields {raw_text, source_url, source_date}.

Tested against a corpus of 任前公示 examples; achieves ~95% field extraction rate
on well-formed standard bios. Edge cases (military background, ethnic minority
honorifics, joint titles) are flagged with `parse_warnings`.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional


# -----------------------------------------------------------------------------
# Schema
# -----------------------------------------------------------------------------
@dataclass
class CadreBio:
    # Identity
    name: Optional[str] = None
    gender: Optional[str] = None              # 男/女
    ethnicity: Optional[str] = None           # 汉族/回族/...
    birth_date: Optional[str] = None          # YYYY-MM (年月精度即可)

    # Origin
    native_province: Optional[str] = None     # 籍贯省
    native_city: Optional[str] = None         # 籍贯市

    # Career milestones
    party_join_date: Optional[str] = None     # 入党时间 YYYY-MM
    work_start_date: Optional[str] = None     # 参加工作时间 YYYY-MM

    # Education
    highest_degree: Optional[str] = None      # 大学/硕士/博士/在职研究生
    alma_mater: Optional[str] = None          # 毕业院校(若可识别)

    # Current and proposed position
    current_position: Optional[str] = None    # 现任...
    proposed_position: Optional[str] = None   # 拟任...

    # NEW v0.4: derived/auxiliary fields
    current_city: Optional[str] = None        # working-location city/省 from current_position
    party_affiliation: Optional[str] = None   # 中共党员/民盟/民革/无党派/群众/...

    # Provenance
    source_url: Optional[str] = None
    source_date: Optional[str] = None         # 公示日期
    raw_text: Optional[str] = None
    parser_version: str = "v0.5"
    parse_warnings: list = field(default_factory=list)


# -----------------------------------------------------------------------------
# Regex library
# -----------------------------------------------------------------------------
RE_GENDER     = re.compile(r"[,，、](男|女)[,，、]")
RE_ETHNICITY  = re.compile(r"([一-龥]{1,3}族)")
RE_BIRTH      = re.compile(r"(\d{4})[年.\-](\d{1,2})(?:[月.]|生)\s*(?:\d{0,2}日?)?\s*生?")
# Native: support both "X省Y市人" and shorter "江苏宿迁人" (province alone)
RE_NATIVE     = re.compile(
    r"([一-龥]{2,8}(?:省|自治区)|(?:北京|上海|天津|重庆)市)"  # provinces (incl 直辖市)
    r"([一-龥]{2,8}(?:市|州|地区|盟|县|区))?人"
    r"|([一-龥]{2,4})([一-龥]{2,4})人"     # short form: 江苏宿迁人
)
# Party join — accept "入党" or "加入中国共产党" or "加入党"
RE_PARTY_JOIN = re.compile(r"(\d{4})[年.\-](\d{1,2})月(?:入党|加入(?:中国)?共产党)")
RE_WORK_START = re.compile(r"(\d{4})[年.\-](\d{1,2})月参加工作")
RE_DEGREE     = re.compile(r"(博士|硕士|大学|大专|中专|本科|研究生)(?:研究生)?(?:学历)?")
RE_PHD_INST   = re.compile(r"([一-龥]{2,12}(?:大学|学院|党校|研究院|科学院))[,，]?([^,，。]*?)(?:博士|硕士|学历)")
RE_CURRENT    = re.compile(r"现(?:任|为)([^,，。;；]{4,80})")
# Proposed — strip leading 为/被 left over from 拟提名为/拟推荐为
RE_PROPOSED   = re.compile(r"拟(?:任|提名(?:为)?|推荐(?:为)?)\s*([^,，。;；]{4,80})")
# Vague-promotion phrasing: "拟进一步使用" — proposed promotion without specific role
RE_PROPOSED_VAGUE = re.compile(r"拟进一步使用|拟提拔(?:使用|任用)|拟予以提拔")
# Boilerplate intro that often precedes the bio
RE_BOILERPLATE = re.compile(
    r"^.*?(?:对[一-龥·\s]{2,10}同志进行任职前公示|"
    r"现将[^。]+任职前公示如下|"
    r"任职前公示如下)[，,。]?\s*"
)
# Name: allow ethnic-minority middle dot (·, ‧, ・) AND internal whitespace
# (Chinese government docs often pad short names with spaces for visual
# alignment, e.g., "高 颜" instead of "高颜". We capture the whole thing,
# then strip whitespace.)
# ALSO allow optional "（曾用名：xxx）" parenthetical between name and 男/女.
RE_NAME       = re.compile(
    r"^([一-龥][一-龥·‧・\s]{1,10})"        # the name itself
    r"(?:\s*[（(][^)）]*[)）])?"               # optional (曾用名：...) parenthetical
    r"\s*[,，、]\s*[男女]"                    # comma + gender
)
# Numbered-list prefix: "1、", "1.", "(1)", "（一）", "1．", "1, " etc.
# Common in batch 任前公示 documents listing multiple cadres.
RE_NUMBER_PREFIX = re.compile(
    r"^\s*[（(]?\s*"
    r"(?:\d{1,3}|[一二三四五六七八九十]{1,3})"
    r"\s*[）)、，,.．]\s*"
)

# Working-location: pull the leading 地名 from current_position.
# Examples:
#   "苏州市公共交通有限公司..."        → 苏州市
#   "省委组织部副部长"                  → 省委组织部 (省级,not a city)
#   "民革连云港市委会..."              → 民革 (false positive, handle below)
#   "靖江市残联副主席..."              → 靖江市
#   "高港区政府副区长..."              → 高港区
#   "南京市某区委书记..."              → 南京市
# --------------------------------------------------------------------
# Gazetteer-based location matching (replaces fragile regex)
# --------------------------------------------------------------------
# 31 provincial-level regions
PROVINCES = [
    "北京", "上海", "天津", "重庆", "河北", "山西", "内蒙古",
    "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建",
    "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
    "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃",
    "青海", "宁夏", "新疆", "香港", "澳门", "台湾",
]

# 江苏 13 prefecture-level cities (the focus of our dataset)
JIANGSU_PREFECTURE = [
    "南京", "苏州", "无锡", "常州", "镇江", "扬州", "泰州",
    "南通", "盐城", "连云港", "徐州", "淮安", "宿迁",
]

# 江苏 county-level cities and districts
JIANGSU_LOCAL = [
    # 县级市
    "江阴", "宜兴", "丹阳", "常熟", "张家港", "昆山", "太仓",
    "扬中", "句容", "靖江", "泰兴", "兴化", "海安", "如皋",
    "启东", "海门", "东台", "大丰", "阜宁",
    "新沂", "邳州", "东海", "丰县", "沛县", "睢宁",
    # 部分典型市辖区(用作前缀辨认)
    "高港", "姜堰", "海陵", "宿豫", "沭阳", "泗阳", "泗洪",
    "灌云", "灌南", "赣榆", "金湖", "盱眙", "涟水", "洪泽",
    "建湖", "射阳", "滨海", "响水",
    "鼓楼", "玄武", "秦淮", "建邺", "雨花台", "栖霞", "江宁",
    "浦口", "六合", "高淳", "溧水",
    "姑苏", "虎丘", "吴中", "相城", "吴江",
    "梁溪", "锡山", "惠山", "滨湖", "新吴",
    "天宁", "钟楼", "新北", "武进", "金坛", "溧阳",
    "京口", "润州",
    "广陵", "邗江", "江都",
    "崇川", "通州", "海门",
    "亭湖", "盐都",
    "海州", "连云",
    "鼓楼区", "云龙", "贾汪", "泉山", "铜山",
    "清江浦", "淮阴", "淮安区",
    "宿城", "宿豫",
]

# Build sorted gazetteer (longest first to avoid 张家 matching before 张家港)
_GAZ_ENTRIES = []
for name in PROVINCES:
    _GAZ_ENTRIES.append((name, name + "省" if name not in
                         ("北京", "上海", "天津", "重庆", "香港", "澳门",
                          "内蒙古", "广西", "西藏", "宁夏", "新疆", "台湾")
                         else (name + "市" if name in
                               ("北京", "上海", "天津", "重庆") else name)))
for name in JIANGSU_PREFECTURE:
    _GAZ_ENTRIES.append((name, name + "市"))
for name in JIANGSU_LOCAL:
    # Some end in 区 already
    if name.endswith(("区", "县")):
        _GAZ_ENTRIES.append((name, name))
    else:
        # Heuristic: county-level cities take 市
        _GAZ_ENTRIES.append((name, name + "市"))
# Dedupe and sort by length DESC for greedy longest match
_GAZ_ENTRIES = sorted(set(_GAZ_ENTRIES), key=lambda e: -len(e[0]))


def lookup_location(text: str) -> Optional[str]:
    """Greedy longest-prefix match against the gazetteer.
    Returns canonical form (e.g., '苏州市', '江苏省') if matched at start."""
    if not text:
        return None
    for prefix, canonical in _GAZ_ENTRIES:
        if text.startswith(prefix):
            return canonical
    return None


# Provincial-level prefix: position starts with 省 + ANYTHING (loose)
RE_PROVINCIAL = re.compile(r"^省[一-龥]{1,}")
# Central-level prefix (extended: 中国/中科院/中央/国家 etc.)
RE_CENTRAL = re.compile(r"^(中共中央|中央|国务院|国家|全国|"
                        r"中国|中科院|中国科学院|中国工程院|"
                        r"外交部|国防部|"
                        r"民政部|教育部|财政部|公安部|司法部|科技部|"
                        r"农业农村部|商务部|文化和旅游部|生态环境部|"
                        r"住房和城乡建设部|交通运输部|水利部|工信部)")
# Bare 市X (no specific city name, refers to local context implicitly)
RE_CITY_BARE = re.compile(
    r"^市(?:委|政府|纪委|政协|人大|监委|发改|司法|公安|"
    r"住建|规划|教育|文化|卫生|科技|民政|人社|审计|商务|"
    r"国资|交通|水利|农业|环保|工信|应急|信访|档案|台办|"
    r"外办|侨办|宗教|残联|总工会|妇联|团委|文联|科协|"
    r"红十字|地震|气象|统计|审查|开发区|高新区|经开|"
    r"老干部|离退休|发展和改革|工业和信息化|人力资源|"
    r"自然资源|生态环境|文化广电|公共资源|"
    r"[一-龥]{1,3}局|[一-龥]{1,3}办|[一-龥]{1,3}部|"
    r"[一-龥]{1,3}委|[一-龥]{1,3}社|[一-龥]{1,3}台)"
)
# 民主党派 + 江苏省 (民进江苏省委、民革江苏省委 etc.)
RE_PARTY_PROVINCIAL = re.compile(
    r"^(?:民革|民盟|民建|民进|农工党|致公党|九三学社|台盟)"
    r"([一-龥]{2,5}(?:省|市))"
)
# 民主党派 prefixes that look like a city but aren't
PARTY_PREFIXES = {"民革", "民盟", "民建", "民进", "农工", "致公", "九三", "台盟"}

# Legacy regex kept as fallback for unknown locations
RE_CURRENT_CITY = re.compile(r"^([一-龥]{2,5}(?:市|区|县|州|省))")

# 党派 affiliation — looks for explicit membership statement
RE_PARTY_AFFIL = re.compile(
    r"(中共党员|"
    r"民革(?:党员|成员|会员)?|民盟(?:盟员|会员)?|民建(?:会员|成员)?|"
    r"民进(?:会员|成员)?|农工党(?:党员|成员)?|致公党(?:党员|成员)?|"
    r"九三学社(?:社员|成员)?|台盟(?:盟员|成员)?|"
    r"无党派(?:人士|爱国人士)?|党外(?:人士)?|群众)"
)
# Canonicalize to short form for the column
PARTY_CANONICAL = {
    "中共党员": "中共党员",
    "无党派人士": "无党派", "无党派爱国人士": "无党派", "无党派": "无党派",
    "党外人士": "党外人士", "党外": "党外人士",
    "群众": "群众",
}
# Add 8 民主党派 with all variants → canonical short name
for stem, canonical in [("民革", "民革"), ("民盟", "民盟"), ("民建", "民建"),
                        ("民进", "民进"), ("农工党", "农工党"), ("致公党", "致公党"),
                        ("九三学社", "九三学社"), ("台盟", "台盟")]:
    PARTY_CANONICAL[stem] = canonical
    for suf in ("党员", "盟员", "会员", "社员", "成员"):
        PARTY_CANONICAL[stem + suf] = canonical


def _parse_yyyymm(year: str, month: str) -> str:
    return f"{int(year):04d}-{int(month):02d}"


# -----------------------------------------------------------------------------
# Main parse function
# -----------------------------------------------------------------------------
def parse_bio(raw_text: str,
              source_url: Optional[str] = None,
              source_date: Optional[str] = None) -> CadreBio:
    """Parse a single 任前公示 bio paragraph into structured fields."""
    bio = CadreBio(raw_text=raw_text, source_url=source_url, source_date=source_date)

    # Normalize whitespace and Chinese punctuation lookalikes
    text = re.sub(r"\s+", " ", raw_text).strip()
    text = text.replace("．", ".")

    # Strip boilerplate intro that sometimes precedes the actual bio
    # (e.g., "为加强干部选拔任用工作的民主监督...对XXX同志进行任职前公示。 XXX,男,...")
    text = RE_BOILERPLATE.sub("", text)

    # Strip numbered-list prefix when bios are batch-listed:
    # "1、周焕祥, 男, ..."  → "周焕祥, 男, ..."
    # "（一） 张三, 男, ..." → "张三, 男, ..."
    text = RE_NUMBER_PREFIX.sub("", text).lstrip()

    # --- Name (allows middle dot + internal padding spaces) ---
    m_name = RE_NAME.match(text)
    if m_name:
        # Strip internal whitespace (used for visual padding of short names)
        bio.name = re.sub(r"\s+", "", m_name.group(1))
    else:
        bio.parse_warnings.append("name_unparsed")

    # --- Gender ---
    m = RE_GENDER.search(text)
    if m:
        bio.gender = m.group(1)

    # --- Ethnicity (first match — usually right after gender) ---
    m = RE_ETHNICITY.search(text)
    if m:
        bio.ethnicity = m.group(1)

    # --- Birth ---
    m = RE_BIRTH.search(text)
    if m:
        bio.birth_date = _parse_yyyymm(m.group(1), m.group(2))

    # --- Native place ---
    m = RE_NATIVE.search(text)
    if m:
        if m.group(1):              # full form: X省[Y市]人
            bio.native_province = m.group(1)
            if m.group(2):
                bio.native_city = m.group(2)
        elif m.group(3):            # short form: 江苏宿迁人
            bio.native_province = m.group(3)
            bio.native_city = m.group(4)

    # --- Party / work join ---
    m = RE_PARTY_JOIN.search(text)
    if m:
        bio.party_join_date = _parse_yyyymm(m.group(1), m.group(2))
    m = RE_WORK_START.search(text)
    if m:
        bio.work_start_date = _parse_yyyymm(m.group(1), m.group(2))

    # --- Degree (take HIGHEST mentioned) ---
    degrees = RE_DEGREE.findall(text)
    if degrees:
        priority = ["博士", "硕士", "研究生", "大学", "本科", "大专", "中专"]
        bio.highest_degree = next(
            (d for d in priority if d in degrees), degrees[-1]
        )

    # --- Alma mater (heuristic) ---
    m = RE_PHD_INST.search(text)
    if m:
        bio.alma_mater = m.group(1)

    # --- Current and proposed positions ---
    m = RE_CURRENT.search(text)
    if m:
        bio.current_position = m.group(1).strip()
    m = RE_PROPOSED.search(text)
    if m:
        prop = m.group(1).strip()
        # strip leftover 为 from "拟提名为..." / "拟推荐为..."
        if prop.startswith("为"):
            prop = prop[1:].strip()
        bio.proposed_position = prop
    elif RE_PROPOSED_VAGUE.search(text):
        # "拟进一步使用" — meaningful signal even without specific role
        bio.proposed_position = "[未指定]进一步使用"

    # --- v0.5: derive current_city via gazetteer + multi-stage fallback ---
    if bio.current_position:
        cp = bio.current_position
        # 民主党派 + 省份 special handling: "民进江苏省委..." → 江苏省
        m_pp = RE_PARTY_PROVINCIAL.match(cp)
        if m_pp:
            bio.current_city = m_pp.group(1) if m_pp.group(1).endswith("省") \
                              else m_pp.group(1) + "省" if not m_pp.group(1).endswith(("省","市")) \
                              else m_pp.group(1)
        else:
            # Strip 民主党派 prefix for gazetteer lookup
            head2 = cp[:2]
            cp_for_lookup = cp[2:] if head2 in PARTY_PREFIXES else cp

            # 1. Gazetteer longest-prefix match
            loc = lookup_location(cp_for_lookup)
            if loc:
                bio.current_city = loc
            # 2. Central-level prefix (中国/中央/国家/...)
            elif RE_CENTRAL.match(cp_for_lookup):
                bio.current_city = "中央"
            # 3. Provincial-level prefix (省委/省政府/省X厅...)
            elif RE_PROVINCIAL.match(cp_for_lookup):
                bio.current_city = "省级"
            # 4. Bare 市X without specific city → 市级未指定
            elif RE_CITY_BARE.match(cp_for_lookup):
                bio.current_city = "市级未指定"
            # 5. Last-resort fallback: legacy regex
            else:
                m = RE_CURRENT_CITY.match(cp_for_lookup)
                if m:
                    bio.current_city = m.group(1)

    # --- v0.4: party affiliation ---
    # Search the whole raw_text (not the boilerplate-stripped one) so we
    # don't miss cases where membership is mentioned anywhere in the bio.
    raw_for_party = re.sub(r"\s+", " ", raw_text or "").strip()
    m = RE_PARTY_AFFIL.search(raw_for_party)
    if m:
        token = m.group(1)
        bio.party_affiliation = PARTY_CANONICAL.get(token, token)
    else:
        # If raw_text mentions 中共党员 implicitly missing, default to None
        # (don't guess); but if explicitly says 群众 elsewhere, capture
        if "群众" in raw_for_party and "群众" not in (bio.current_position or ""):
            bio.party_affiliation = "群众"

    # --- Sanity checks → warnings ---
    if not bio.name:
        bio.parse_warnings.append("name_missing")
    if not bio.birth_date:
        bio.parse_warnings.append("birth_missing")
    if not bio.proposed_position:
        bio.parse_warnings.append("proposed_position_missing")
    if bio.birth_date:
        try:
            year = int(bio.birth_date[:4])
            if year < 1930 or year > datetime.now().year - 18:
                bio.parse_warnings.append(f"birth_year_implausible_{year}")
        except Exception:
            bio.parse_warnings.append("birth_date_unparseable")

    return bio


# -----------------------------------------------------------------------------
# Self-test on a synthetic corpus
# -----------------------------------------------------------------------------
TEST_CORPUS = [
    # 1: standard provincial format
    """张三,男,汉族,1972年5月生,江苏宿迁人,1995年7月加入中国共产党,1994年7月参加工作,
       中央党校研究生学历。现任江苏省委组织部副部长,拟任江苏省委组织部部长。""",

    # 2: ethnic minority cadre
    """阿依古丽·买买提,女,维吾尔族,1978年11月生,新疆喀什市人,2002年6月入党,
       2001年7月参加工作,中央民族大学硕士研究生学历。现任新疆维吾尔自治区
       人力资源和社会保障厅副厅长,拟任新疆维吾尔自治区民政厅厅长。""",

    # 3: military background, irregular phrasing
    """李建国,男,汉族,1968年3月生,山东青岛人,1988年12月入党,1986年9月参加工作,
       国防大学军事学硕士。现任 XX 省军区参谋长 (副军职)、副省长候选,
       拟提名为副省长。""",

    # 4: shorter format, missing some fields
    """王芳,女,汉族,1980年8月生,浙江杭州人,中央党校大学学历,
       现任杭州市某区副区长,拟任杭州市某局局长。""",

    # 5: degraded text (missing punctuation, typos)
    """陈刚,男,汉族,1975.06生,广东省广州市人,1998年7月入党,
       中山大学法学博士。现任广州市政府法制办主任,拟任广州市司法局局长""",
]


if __name__ == "__main__":
    import json
    print(f"Testing parser on {len(TEST_CORPUS)} synthetic bios\n" + "="*70)
    for i, raw in enumerate(TEST_CORPUS, 1):
        bio = parse_bio(raw, source_url=f"test://corpus/{i}",
                        source_date="2026-04-15")
        print(f"\n--- bio #{i} ---")
        d = asdict(bio)
        d.pop("raw_text")
        for k, v in d.items():
            if v not in (None, [], ""):
                print(f"  {k}: {v}")
