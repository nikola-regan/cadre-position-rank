"""
Parser for Baidu Baike biographical entries (官员条目).

Extracts:
  - Basic info (姓名、出生年月、籍贯、民族、学历, etc.) from the lemma summary
    and the right-side info-box.
  - Career chronology (人物经历 section): list of (start, end, org, position)
    tuples.

Multiple HTML structures used by Baike over time, so we use multi-strategy
fallbacks.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


# -------------------------------------------------------------------------
# Date parsing: handle various Baike date formats
# -------------------------------------------------------------------------
RE_DATE_RANGE = re.compile(
    r"(\d{4})\s*[\.年/\-]\s*(\d{1,2})?\s*(?:月)?"   # start  YYYY[.M]
    r"\s*[—\-－~至]\s*"                                # separator
    r"(?:(\d{4})\s*[\.年/\-]\s*(\d{1,2})?\s*(?:月)?|至今|现在|今)"   # end
)
RE_DATE_SINGLE = re.compile(
    r"(\d{4})\s*[\.年/\-]\s*(\d{1,2})\s*(?:月)?"
)


def _yyyymm(year: str, month: Optional[str]) -> str:
    if not year:
        return ""
    return f"{int(year):04d}-{int(month):02d}" if month else f"{int(year):04d}"


# -------------------------------------------------------------------------
# Schema
# -------------------------------------------------------------------------
@dataclass
class BaikeBasicInfo:
    name: Optional[str] = None
    gender: Optional[str] = None
    ethnicity: Optional[str] = None
    birth_date: Optional[str] = None
    native_place: Optional[str] = None
    party_join_date: Optional[str] = None
    work_start_date: Optional[str] = None
    highest_degree: Optional[str] = None
    alma_mater: Optional[str] = None


@dataclass
class CareerSpell:
    spell_idx: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    organization: Optional[str] = None
    position: Optional[str] = None
    raw_line: Optional[str] = None


@dataclass
class BaikePerson:
    basic: BaikeBasicInfo = field(default_factory=BaikeBasicInfo)
    career: list[CareerSpell] = field(default_factory=list)
    source_url: Optional[str] = None
    parser_version: str = "v0.1"
    parse_warnings: list = field(default_factory=list)


# -------------------------------------------------------------------------
# Basic-info extraction (from summary text + info-box)
# -------------------------------------------------------------------------
RE_BIRTH    = re.compile(r"(\d{4})[年.\-](\d{1,2})月(?:\d{0,2}日?)?生")
RE_PARTY    = re.compile(r"(\d{4})[年.\-](\d{1,2})月(?:加入(?:中国)?共产党|入党)")
RE_WORK     = re.compile(r"(\d{4})[年.\-](\d{1,2})月参加工作")
RE_DEGREE   = re.compile(r"(博士|硕士|研究生|大学|本科|大专|中专)")
RE_ETHNICITY = re.compile(r"([一-龥]{1,3}族)")
RE_NATIVE   = re.compile(
    r"([一-龥]{2,8}(?:省|自治区|市))(?:([一-龥]{2,8}(?:市|州|地区|盟|县|区)))?人"
    r"|([一-龥]{2,4})([一-龥]{2,4})人"
)


def parse_basic_info(text: str) -> BaikeBasicInfo:
    info = BaikeBasicInfo()

    if (m := RE_BIRTH.search(text)):
        info.birth_date = _yyyymm(m.group(1), m.group(2))
    if (m := RE_PARTY.search(text)):
        info.party_join_date = _yyyymm(m.group(1), m.group(2))
    if (m := RE_WORK.search(text)):
        info.work_start_date = _yyyymm(m.group(1), m.group(2))
    if (m := RE_ETHNICITY.search(text)):
        info.ethnicity = m.group(1)
    if (m := re.search(r"[,，、](男|女)[,，、]", text)):
        info.gender = m.group(1)
    if (m := RE_NATIVE.search(text)):
        if m.group(1):
            info.native_place = (m.group(1) + (m.group(2) or "")).strip()
        elif m.group(3):
            info.native_place = (m.group(3) + (m.group(4) or "")).strip()
    degrees = RE_DEGREE.findall(text)
    if degrees:
        priority = ["博士", "硕士", "研究生", "大学", "本科", "大专", "中专"]
        info.highest_degree = next((d for d in priority if d in degrees), degrees[-1])

    return info


# -------------------------------------------------------------------------
# Career-line parsing
# -------------------------------------------------------------------------
def parse_career_line(line: str) -> Optional[tuple[str, str, str, str]]:
    """Parse one '人物经历' line into (start, end, org, position).
    Returns None if line doesn't look like a career entry."""
    line = re.sub(r"\s+", " ", line.strip())
    if len(line) < 10:
        return None

    # Try date range
    m = RE_DATE_RANGE.search(line)
    if not m:
        return None
    start = _yyyymm(m.group(1), m.group(2))
    if m.group(3):
        end = _yyyymm(m.group(3), m.group(4))
    else:
        end = "至今"

    # Strip the date part to get the rest
    rest = line[m.end():].strip(",，、 :：")

    # Heuristic split: org <space/，> position
    # Common formats:
    #   "江苏省宿迁市XX乡 团委干事"
    #   "江苏省宿迁市XX乡，团委副书记"
    #   "江苏省XX局，副局长"
    parts = re.split(r"[,，、；; ]+", rest, maxsplit=1)
    if len(parts) == 2:
        org, pos = parts
    else:
        # Heuristic: position keywords usually come last
        pos_match = re.search(
            r"((?:副?(?:省长|市长|区长|县长|乡长|镇长|主任|部长|局长|"
            r"书记|副书记|常委|常务|秘书|主席|院长|检察长|庭长|厅长|处长|"
            r"科长|主管|总经理|董事长|社长|总编辑|党组|党委))[一-龥、(（)）]*)$",
            rest,
        )
        if pos_match:
            pos = pos_match.group(1)
            org = rest[: pos_match.start()].strip(" ,，、")
        else:
            # Couldn't split — put whole thing in position
            org, pos = "", rest

    return start, end, org.strip(), pos.strip()


# -------------------------------------------------------------------------
# Top-level: extract career section
# -------------------------------------------------------------------------
def extract_career_section(html: str) -> list[str]:
    """Find the 人物经历 / 履历 / 任免信息 / 工作经历 section and return its
    raw lines (each line should contain one career spell)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    HEADERS = ("人物经历", "履历", "任免信息", "工作经历", "个人履历", "工作简历")

    # Strategy 1: find a header (h1/h2/h3 or .para-title) matching one of HEADERS
    header_tag = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if any(text.startswith(h) for h in HEADERS):
            header_tag = tag
            break
    if not header_tag:
        for tag in soup.select(".para-title, .lemmaWgt-list-title"):
            text = tag.get_text(strip=True)
            if any(text.startswith(h) for h in HEADERS):
                header_tag = tag
                break

    if header_tag:
        # Collect ONLY leaf nodes (no children with date ranges) to avoid
        # capturing both a container div AND its child <p>'s.
        lines = []
        for sib in header_tag.find_all_next():
            if sib is header_tag:
                continue
            if sib.name in ("h1", "h2", "h3", "h4"):
                t = sib.get_text(strip=True)
                if t and not any(t.startswith(h) for h in HEADERS):
                    break  # next section starts
            # Skip if this node has descendants that themselves contain dates
            descendants_with_dates = sum(
                1 for child in sib.find_all(["p", "li", "div", "span"])
                if RE_DATE_RANGE.search(child.get_text("", strip=True) or "")
            )
            if descendants_with_dates >= 1:
                continue   # let the children speak; this is a container
            txt = sib.get_text(separator="", strip=True)
            if not txt or len(txt) > 350:
                continue
            if RE_DATE_RANGE.search(txt) or RE_DATE_SINGLE.search(txt):
                lines.append(txt)
        return lines

    # Strategy 2: scan all <p>/<li> looking for date-ranges
    lines = []
    for tag in soup.find_all(["p", "li", "div"]):
        text = tag.get_text(separator="", strip=True)
        if not text or len(text) < 10 or len(text) > 400:
            continue
        if RE_DATE_RANGE.search(text):
            lines.append(text)
    return lines


def parse_baike_entry(html: str, source_url: Optional[str] = None) -> BaikePerson:
    """Top-level entry parser. Combines basic info + career chronology."""
    from bs4 import BeautifulSoup

    person = BaikePerson(source_url=source_url)
    soup = BeautifulSoup(html, "html.parser")

    # --- Summary text for basic info -----------------------------------
    summary = ""
    for sel in [".lemma-summary", ".lemma-desc", ".lemmaSummary",
                ".basicInfo", "div[class*='summary']"]:
        node = soup.select_one(sel)
        if node:
            summary += node.get_text(separator=" ", strip=True) + " "
    if not summary:
        # Fallback: take first 1500 chars of body text
        summary = soup.get_text(separator=" ", strip=True)[:1500]

    person.basic = parse_basic_info(summary)

    # --- Try to read explicit name from page title ---------------------
    title = soup.find("h1") or soup.find("title")
    if title:
        t = title.get_text(strip=True)
        # Often "人名_百度百科" or just "人名"
        t = re.sub(r"_百度百科$", "", t)
        m = re.match(r"^([一-龥·\s]{2,12})", t)
        if m:
            person.basic.name = re.sub(r"\s+", "", m.group(1))

    # --- Career chronology --------------------------------------------
    lines = extract_career_section(html)
    for i, ln in enumerate(lines, start=1):
        parsed = parse_career_line(ln)
        if not parsed:
            continue
        start, end, org, pos = parsed
        person.career.append(CareerSpell(
            spell_idx=i,
            start_date=start, end_date=end,
            organization=org, position=pos,
            raw_line=ln[:300],
        ))

    if not person.career:
        person.parse_warnings.append("no_career_extracted")
    if not person.basic.name:
        person.parse_warnings.append("name_missing")

    return person


# -------------------------------------------------------------------------
# Self-test
# -------------------------------------------------------------------------
if __name__ == "__main__":
    from baike_fetcher import MockBaikeFetcher
    f = MockBaikeFetcher(cache_dir="/tmp/baike_test")
    html = f.fetch("https://baike.baidu.com/item/张三/12345")
    person = parse_baike_entry(html, source_url="mock://item/张三")
    print(f"=== Basic info ===")
    for k, v in person.basic.__dict__.items():
        if v: print(f"  {k}: {v}")
    print(f"\n=== Career chronology ({len(person.career)} spells) ===")
    for s in person.career:
        print(f"  {s.spell_idx:2d}. {s.start_date} → {s.end_date}  "
              f"{s.organization:30s} {s.position}")
    if person.parse_warnings:
        print(f"\nWarnings: {person.parse_warnings}")
