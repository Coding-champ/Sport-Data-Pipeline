from __future__ import annotations

"""Asynchroner Club-Scraper für bundesliga.com (Übersicht + Detailseiten)

Architektur analog zu `BundesligaMatchdayScraper` unter Nutzung von `BaseScraper`.
Strategie:
 1. Clubs von Übersicht: statische Links / heuristische Selektoren / JSON-Fallback
 2. Für jeden Club Detailseite laden und Kerninfos extrahieren
 3. Rückgabe strukturierter Dictionaries (für spätere DB-Persistierung)

Hinweis: Bundesliga nutzt dynamisches Frontend -> häufig liegen Daten in einem Hydration-Objekt (window.__NUXT__ o.ä.).
Dieser Scraper versucht einfache statische Extraktion; falls leer, kann später Playwright integriert oder eine API identifiziert werden.
"""

import os
import re
import json
import logging
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

try:  # preferred absolute import when run as module
    from src.data_collection.scrapers.base import BaseScraper, ScrapingConfig  # type: ignore
except ImportError:
    # Fallback: ensure project root (the folder containing 'src') is on sys.path
    current_file = os.path.abspath(__file__)
    # ascend until we find 'src'
    candidate = current_file
    for _ in range(6):
        candidate = os.path.dirname(candidate)
        if os.path.isdir(os.path.join(candidate, 'src')):
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
            break
    try:
        from src.data_collection.scrapers.base import BaseScraper, ScrapingConfig  # type: ignore
    except ImportError:
        # Last resort: relative import if executed inside package context via -m
        from ..base import BaseScraper, ScrapingConfig  # type: ignore


logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# -------------------- Config --------------------
@dataclass
class BundesligaClubScraperConfig(ScrapingConfig):
    base_url: str = "https://www.bundesliga.com"
    selectors: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    delay_range: tuple = (1, 2)
    max_retries: int = 3
    timeout: int = 30
    use_proxy: bool = False
    proxy_list: Optional[list[str]] = None
    anti_detection: bool = True
    screenshot_on_error: bool = False


class BundesligaClubScraper(BaseScraper):
    name = "bundesliga_clubs"

    OVERVIEW_URL = "https://www.bundesliga.com/en/bundesliga/clubs"

    def __init__(self, db_manager, save_html: bool = False):
        cfg = BundesligaClubScraperConfig()
        super().__init__(cfg, db_manager=db_manager, name=self.name)
        self.save_html = save_html or bool(os.getenv("BUNDESLIGA_SCRAPER_SAVE_HTML"))
        # Playwright fallback toggle via env
        self._use_playwright = os.getenv("BUNDESLIGA_USE_PLAYWRIGHT", "0") in ("1", "true", "True")
        self._pw = None
        self._pw_browser = None
        self._pw_page = None

    async def _ensure_playwright(self):
        if not self._use_playwright:
            return False
        if self._pw_page is not None:
            return True
        try:
            self._pw = await async_playwright().start()
            self._pw_browser = await self._pw.chromium.launch(headless=True)
            self._pw_page = await self._pw_browser.new_page()
            return True
        except Exception as e:
            self.logger.warning(f"Playwright init failed: {e}")
            return False

    async def _close_playwright(self):
        try:
            if self._pw_page:
                await self._pw_page.close()
            if self._pw_browser:
                await self._pw_browser.close()
            if self._pw:
                await self._pw.stop()
        finally:
            self._pw = None
            self._pw_browser = None
            self._pw_page = None

    async def _rendered_html(self, url: str) -> Optional[str]:
        ok = await self._ensure_playwright()
        if not ok or not self._pw_page:
            return None
        try:
            await self._pw_page.goto(url, wait_until="domcontentloaded")
            # small wait for Angular/CSR
            await asyncio.sleep(1.0)
            return await self._pw_page.content()
        except Exception as e:
            self.logger.warning(f"Playwright fetch failed for {url}: {e}")
            return None

    # -------------------- Public Entry Point --------------------
    async def scrape_data(self) -> list[dict]:  # type: ignore[override]
        html = await self.fetch_page(self.OVERVIEW_URL)
        soup = self.parse_html(html)
        clubs = self._extract_clubs_overview(soup, raw_html=html)
        results: list[dict] = []
        for c in clubs:
            url = c.get("url")
            if not url:
                continue
            try:
                detail_html = await self.fetch_page(url)
                if self.save_html:
                    try:
                        os.makedirs('reports/bundesliga/clubs', exist_ok=True)
                        slug = url.rstrip('/').split('/')[-1]
                        with open(f'reports/bundesliga/clubs/{slug}.html', 'w', encoding='utf-8') as f:
                            f.write(detail_html)
                    except Exception as _e:
                        self.logger.debug(f"Failed saving detail HTML for {url}: {_e}")
                detail = self._parse_detail(detail_html, url)
                # If profile_info empty and playwright enabled, try rendered HTML once
                if detail and not detail.get('profile_info') and self._use_playwright:
                    rendered = await self._rendered_html(url)
                    if rendered:
                        if self.save_html:
                            try:
                                slug = url.rstrip('/').split('/')[-1]
                                with open(f'reports/bundesliga/clubs/{slug}__rendered.html', 'w', encoding='utf-8') as f:
                                    f.write(rendered)
                            except Exception:
                                pass
                        detail2 = self._parse_detail(rendered, url)
                        if detail2 and detail2.get('profile_info'):
                            # prefer rendered profile
                            detail['profile_info'] = detail2['profile_info']
                            # also propagate flattened keys
                            for k in ('full_name','capacity','club_colors','address','street','city','phone','fax','email','website','stadium'):
                                if k in detail2:
                                    detail[k] = detail2[k]
                if detail:
                    detail.update({
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "source": "bundesliga",
                    })
                    # Merge overview basics
                    for k, v in c.items():
                        detail.setdefault(k, v)
                    results.append(detail)
                await self.anti_detection.random_delay(self.config.delay_range)
            except Exception as e:
                self.logger.warning(f"Failed club detail {url}: {e}")
                continue
        return results

    async def cleanup(self):
        await super().cleanup()
        if self._pw or self._pw_browser or self._pw_page:
            await self._close_playwright()

    # -------------------- Overview Extraction --------------------
    def _extract_clubs_overview(self, soup: BeautifulSoup, raw_html: str) -> list[dict]:
        clubs: list[dict] = []
        debug = bool(os.getenv("BUNDESLIGA_DEBUG"))
        skipped_no_url = 0
        skipped_no_name = 0
        # Heuristic selectors
        tried_selectors = [
            '.club-card',
            '[data-component="ClubCard"]',
            'a[href*="/en/bundesliga/clubs/"]'
        ]
        for sel in tried_selectors:
            els = soup.select(sel)
            if els:
                self.logger.info("Overview selector '%s' -> %d elements", sel, len(els))
                for el in els:
                    url = self._extract_detail_url(el)
                    if not url:
                        skipped_no_url += 1
                        continue
                    name = self._extract_name(el)
                    if not name:
                        # fallback: anchor text if element is <a>
                        if el.name == 'a':
                            txt = el.get_text(strip=True)
                            if txt and len(txt) < 60 and '/' not in txt:
                                name = txt
                    if not name:
                        skipped_no_name += 1
                        continue
                    stadium = self._extract_stadium(el)
                    clubs.append({"name": name, "stadium": stadium, "url": url})
                break
        if clubs:
            if debug:
                self.logger.info("Collected %d clubs (skipped: no_url=%d, no_name=%d)", len(clubs), skipped_no_url, skipped_no_name)
            return self._dedupe(clubs)
        self.logger.warning("Static overview selectors found no clubs – trying JSON fallback")
        if self.save_html:
            # Save overview HTML for manual inspection
            out_dir = os.path.join('reports', 'bundesliga')
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, 'clubs_overview_raw.html'), 'w', encoding='utf-8') as f:
                f.write(raw_html)
        return self._json_overview_fallback(raw_html)

    def _json_overview_fallback(self, html: str) -> list[dict]:
        # Use greedy match to capture the full JSON object before </script>
        pattern = re.compile(r'window\.__NUXT__\s*=\s*(\{.*\})\s*</script>', re.DOTALL)
        m = pattern.search(html)
        if not m:
            return []
        try:
            data = json.loads(m.group(1))
        except Exception:
            return []
        found: list[dict] = []

        def walk(obj):
            if isinstance(obj, dict):
                if {"slug", "name"} <= obj.keys():
                    slug = obj.get("slug")
                    if isinstance(slug, str):
                        if slug.startswith("/en/bundesliga/clubs/"):
                            url = f"https://www.bundesliga.com{slug}" if slug.startswith('/') else slug
                        elif slug.startswith('/'):
                            url = f"https://www.bundesliga.com{slug}" if '/bundesliga/clubs/' in slug else None
                        else:
                            url = f"https://www.bundesliga.com/en/bundesliga/clubs/{slug}"
                        if url and '/en/bundesliga/clubs/' in url:
                            found.append({
                                "name": str(obj.get('name', '')).strip(),
                                "stadium": str(obj.get('stadium', '') or '').strip(),
                                "url": url
                            })
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for it in obj:
                    walk(it)
        walk(data)
        deduped = self._dedupe(found)
        self.logger.info("JSON fallback extracted %d clubs", len(deduped))
        return deduped

    # -------------------- Detail Parsing --------------------
    def _parse_detail(self, html: str, url: str) -> Optional[dict]:
        soup = self.parse_html(html)
        name = self._first_text(soup, [
            '.club-profile__name', 'h1', 'h1[class*="club"]'
        ])
        main_links = soup.select_one('.quicklink-group.main, .quicklink-group.main-links, [class*="quicklink-group"][class*="main"]')
        social_links_container = soup.select_one('.quicklink-group.social, .quicklink-group.social-links, [class*="quicklink-group"][class*="social"]')
        website: Optional[str] = None
        social: dict[str, str] = {}

        # Main (website) links
        if main_links:
            for a in main_links.select('a[href]'):
                href = (a.get('href') or '').strip()
                if not href:
                    continue
                txt = a.get_text(strip=True).lower()
                if href.startswith('//'):
                    href = 'https:' + href
                if website is None and (re.search(r'website|official', txt) or re.search(r'https?://[^\s]+', href)):
                    website = href

        # Social links (normalize twitter/x)
        def _social_key(h: str) -> Optional[str]:
            low = h.lower()
            mapping = {
                'x.com': 'twitter',
                'twitter.com': 'twitter',
                'facebook.com': 'facebook',
                'instagram.com': 'instagram',
                'tiktok.com': 'tiktok',
                'youtube.com': 'youtube',
                'linkedin.com': 'linkedin'
            }
            for dom, key in mapping.items():
                if dom in low:
                    return key
            return None

        containers = []
        if social_links_container:
            containers.append(social_links_container)
        else:
            # fallback search region
            containers.append(soup)
        for cont in containers:
            for a in cont.select('a[href*="twitter"],a[href*="x.com"],a[href*="facebook"],a[href*="instagram"],a[href*="tiktok"],a[href*="youtube"],a[href*="linkedin"]'):
                href = (a.get('href') or '').strip()
                if not href:
                    continue
                if href.startswith('//'):
                    href = 'https:' + href
                key = _social_key(href)
                if key and key not in social:
                    social[key] = href

        if not website:
            website = self._first_attr(soup, ['.club-profile__website a', 'a[rel*="external"]'], 'href')

        season_stats = self._extract_season_stats(soup)
        profile_info: dict[str, Any] = {}

        profile_section = soup.select_one('section#profile, section#Profile, section.profile, section[id*="profile"], div[id*="profile"], article[id*="profile"]')
        # If no explicit profile section found, attempt content-based detection: a container with known labels
        if not profile_section:
            known_labels_set = { 'full name','founded','club colors','street','city','directions','phone','fax','website','email' }
            candidates = soup.select('section, div, article')
            best_node = None
            best_score = 0
            for node in candidates:
                labels = [el.get_text(strip=True).strip().lower() for el in node.select('.label')]
                if not labels:
                    continue
                score = sum(1 for t in labels if t in known_labels_set)
                if score > best_score:
                    best_score = score
                    best_node = node
            if best_node and best_score >= 2:
                profile_section = best_node
        if profile_section:
            stadium_val = profile_section.select_one('.stadium-name-wrapper .value')
            if stadium_val and (sv := stadium_val.get_text(strip=True)):
                profile_info['stadium'] = sv
            # Collect candidate row containers (support both factTable and plain row/col layout)
            candidate_rows = profile_section.select('.factTable .col, .factTable [class*="col-"], .row > .col, .row > [class*="col-"]')
            if not candidate_rows:
                # fallback: any direct children with a .label inside
                candidate_rows = [d for d in profile_section.select('div') if d.select_one('.label') and d.select_one('.value')]
            for row in candidate_rows:
                label_el = row.select_one('.label')
                value_el = row.select_one('.value')
                if not label_el or not value_el:
                    continue
                label_txt_raw = label_el.get_text(strip=True)
                if not label_txt_raw:
                    continue
                norm_label = label_txt_raw.lower().strip().replace(' ', '_')
                if 'color' in norm_label:
                    colors = []
                    for cc in value_el.select('.clubColor'):
                        style = cc.get('style', '')
                        m = re.search(r'background-color:\s*([^;]+);?', style)
                        if m:
                            col_raw = m.group(1).strip()
                            # Convert rgb(a) to hex if possible
                            rgb_match = re.match(r'rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', col_raw)
                            if rgb_match:
                                r, g, b = [int(x) for x in rgb_match.groups()]
                                r = max(0, min(r,255)); g = max(0, min(g,255)); b = max(0, min(b,255))
                                colors.append(f"#{r:02X}{g:02X}{b:02X}")
                            else:
                                colors.append(col_raw)
                    if colors:
                        profile_info['club_colors'] = colors
                    continue
                a = value_el.find('a', href=True)
                if a:
                    href = a['href']
                    if href.startswith('mailto:'):
                        profile_info['email'] = href.replace('mailto:', '').strip()
                        continue
                    if 'maps.google' in href or 'google.com/maps' in href:
                        profile_info['maps_link'] = href
                        txt = a.get_text(strip=True)
                        if txt:
                            profile_info[norm_label] = txt
                        continue
                    if norm_label == 'website' and not website:
                        website = href
                        profile_info['website'] = href
                        continue
                raw_val = value_el.get_text(' ', strip=True)
                if raw_val:
                    if norm_label == 'capacity':
                        cleaned = re.sub(r'[\u2009\u00a0]', ' ', raw_val)
                        digits = re.sub(r'[^0-9]', '', cleaned)
                        profile_info['capacity'] = digits or cleaned.strip()
                    elif norm_label in ('full_name','street','city','phone','fax','email','website'):
                        profile_info[norm_label] = raw_val
                    else:
                        profile_info[norm_label] = raw_val
            if os.getenv('BUNDESLIGA_PROFILE_DEBUG'):
                self.logger.info("Profile primary pass rows=%d parsed_keys=%d for %s", len(candidate_rows), len(profile_info), url)

            # Additional pass: scan explicit label/value sibling pairs within the same parent
            known_labels = {
                'full name','founded','club colors','street','city','directions','phone','fax','website','email'
            }
            for label_el in profile_section.select('.label'):
                lab_text = label_el.get_text(strip=True)
                if not lab_text:
                    continue
                lab_lower = lab_text.strip().lower()
                if lab_lower not in known_labels:
                    continue
                parent = label_el.parent
                value_el = None
                # Prefer immediate next sibling with class value
                for sib in label_el.next_siblings:
                    try:
                        classes = getattr(sib, 'get', lambda *_: None)('class') or []
                    except Exception:
                        classes = []
                    if isinstance(classes, list) and 'value' in classes:
                        value_el = sib
                        break
                if not value_el and parent:
                    # fallback: a .value within the same parent container
                    value_el = parent.find(class_=lambda c: c and isinstance(c, list) and 'value' in c)
                if not value_el:
                    continue
                norm_label = lab_lower.replace(' ', '_')
                # Colors special-case
                if 'color' in norm_label:
                    colors = []
                    for cc in getattr(value_el, 'select', lambda *_: [])('.clubColor'):
                        style = cc.get('style', '')
                        m = re.search(r'background-color:\s*([^;]+);?', style)
                        if m:
                            col_raw = m.group(1).strip()
                            rgb_match = re.match(r'rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', col_raw)
                            if rgb_match:
                                r, g, b = [int(x) for x in rgb_match.groups()]
                                r = max(0, min(r,255)); g = max(0, min(g,255)); b = max(0, min(b,255))
                                colors.append(f"#{r:02X}{g:02X}{b:02X}")
                            else:
                                colors.append(col_raw)
                    if colors:
                        profile_info['club_colors'] = colors
                    continue
                # Anchor-based values
                a = getattr(value_el, 'find', lambda *_: None)('a', href=True) if value_el else None
                if a:
                    href = a.get('href', '')
                    if 'google.com/maps' in href:
                        profile_info['maps_link'] = href
                        continue
                    if norm_label == 'website':
                        profile_info['website'] = href
                        if not website:
                            website = href
                        continue
                raw_val = getattr(value_el, 'get_text', lambda *_: '')(' ', strip=True)
                if raw_val:
                    if norm_label == 'founded':
                        # try int
                        try:
                            profile_info['founded'] = int(re.sub(r'[^0-9]', '', raw_val))
                        except Exception:
                            profile_info['founded'] = raw_val
                    else:
                        profile_info[norm_label] = raw_val

        # If no keys yet but section exists, attempt lightweight fallback strictly within profile section
        if not profile_info and profile_section:
            fallback_rows = profile_section.select('.row > .col, .row > [class*="col-"]')
            parsed_any = False
            for row in fallback_rows:
                label_el = row.select_one('.label')
                value_el = row.select_one('.value')
                if not label_el or not value_el:
                    continue
                label_txt_raw = label_el.get_text(strip=True)
                if not label_txt_raw:
                    continue
                norm_label = label_txt_raw.lower().strip().replace(' ', '_')
                if 'color' in norm_label:
                    colors = []
                    for cc in value_el.select('.clubColor'):
                        style = cc.get('style','')
                        m = re.search(r'background-color:\s*([^;]+);?', style)
                        if m:
                            col_raw = m.group(1).strip()
                            rgb_match = re.match(r'rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', col_raw)
                            if rgb_match:
                                r, g, b = [int(x) for x in rgb_match.groups()]
                                colors.append(f"#{r:02X}{g:02X}{b:02X}")
                            else:
                                colors.append(col_raw)
                    if colors:
                        profile_info['club_colors'] = colors
                    parsed_any = True
                    continue
                a = value_el.find('a', href=True)
                if a and 'google.com/maps' in a['href']:
                    profile_info['maps_link'] = a['href']
                raw_val = value_el.get_text(' ', strip=True)
                if raw_val:
                    if norm_label == 'capacity':
                        cleaned = re.sub(r'[\u2009\u00a0]', ' ', raw_val)
                        digits = re.sub(r'[^0-9]', '', cleaned)
                        profile_info['capacity'] = digits or cleaned.strip()
                    else:
                        profile_info[norm_label] = raw_val
                    parsed_any = True
            if os.getenv('BUNDESLIGA_PROFILE_DEBUG') and not parsed_any:
                self.logger.warning("Profile fallback parsed 0 rows for %s", url)

        # Generic last-resort scan strictly within profile section
        if not profile_info and profile_section:
            generic_pairs = []
            for pair in profile_section.select('.label + .value, .label ~ .value'):
                label_el = pair.find_previous_sibling(class_='label') if pair and pair.parent else None
                if not label_el:
                    continue
                k = label_el.get_text(strip=True)
                v = pair.get_text(' ', strip=True)
                if k and v:
                    nk = k.lower().strip().replace(' ', '_')
                    if nk not in profile_info:
                        profile_info[nk] = v
                        generic_pairs.append(nk)
            if os.getenv('BUNDESLIGA_PROFILE_DEBUG'):
                self.logger.info("Generic fallback added %d keys for %s", len(generic_pairs), url)

        # Aggregate address if street + city present
        if 'street' in profile_info and 'city' in profile_info and 'address' not in profile_info:
            profile_info['address'] = f"{profile_info['street']}, {profile_info['city']}"

        if 'stadium' not in profile_info and 'stadium' in season_stats:
            profile_info['stadium'] = season_stats['stadium']

        # JSON-based fallbacks for profile info if DOM-based parsing yielded nothing
        if not profile_info:
            prof_ld = self._extract_profile_from_ldjson(soup)
            if prof_ld:
                # normalize and merge
                if 'website' in prof_ld and not website:
                    website = prof_ld.get('website')
                profile_info.update(prof_ld)
                if os.getenv('BUNDESLIGA_PROFILE_DEBUG'):
                    self.logger.info("Profile info populated from LD-JSON for %s (keys=%d)", url, len(profile_info))
        if not profile_info:
            prof_hyd = self._extract_profile_from_hydration(html)
            if prof_hyd:
                if 'website' in prof_hyd and not website:
                    website = prof_hyd.get('website')
                profile_info.update(prof_hyd)
                if os.getenv('BUNDESLIGA_PROFILE_DEBUG'):
                    self.logger.info("Profile info populated from hydration JSON for %s (keys=%d)", url, len(profile_info))

        if not name:
            for s in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(s.string or '{}')
                except Exception:
                    continue
                if isinstance(data, dict) and data.get('@type') in ('SportsTeam','Organization') and data.get('name'):
                    name = data.get('name')
                    break
        if not name and soup.title and ' - ' in soup.title.get_text():
            name = soup.title.get_text().split(' - ')[0].strip()
        if not name:
            return None
        return {
            "name": name,
            "website": website,
            "social_links": social,
            "season_stats": season_stats,
            "profile_info": profile_info,
            # Flatten frequently used fields for easier downstream consumption
            **{k: v for k, v in profile_info.items() if k in (
                'full_name','founded','capacity','club_colors','address','street','city','phone','fax','email','website','stadium'
            )},
            "url": url
        }

    # -------------------- Helpers --------------------
    def _extract_detail_url(self, el) -> Optional[str]:
        # If element itself is an anchor
        if getattr(el, 'name', None) == 'a' and el.get('href'):
            href = el.get('href').split('?')[0]
        else:
            a = el.find('a', href=True)
            if not a:
                return None
            href = a['href'].split('?')[0]
        if not href.startswith('http'):
            href = f"https://www.bundesliga.com{href}" if href.startswith('/') else f"https://www.bundesliga.com{('/' + href) if not href.startswith('/') else href}"
        if '/en/bundesliga/clubs/' not in href:
            return None
        return href

    def _extract_name(self, el) -> Optional[str]:
        for sel in ('.club-card__name', '.name', 'h3', 'span'):
            node = el.select_one(sel)
            if node and (txt := node.get_text(strip=True)):
                return txt
        img = el.find('img', alt=True)
        if img:
            return img['alt']
        return None

    def _extract_stadium(self, el) -> Optional[str]:
        for sel in ('.club-card__stadium', '.stadium', '[data-testid="stadium"]'):
            node = el.select_one(sel)
            if node and (txt := node.get_text(strip=True)):
                return txt
        return None

    def _dedupe(self, items: list[dict]) -> list[dict]:
        seen = set()
        out = []
        for it in items:
            u = it.get('url')
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(it)
        return out

    def _first_text(self, soup: BeautifulSoup, selectors: list[str]) -> Optional[str]:
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(strip=True)
                if txt:
                    return txt
        return None

    def _first_attr(self, soup: BeautifulSoup, selectors: list[str], attr: str) -> Optional[str]:
        for sel in selectors:
            el = soup.select_one(sel)
            if el and el.get(attr):
                return el.get(attr)
        return None

    def _extract_season_stats(self, soup: BeautifulSoup) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        stats_section = soup.select_one('section#stats, section.stats')
        debug = bool(os.getenv('BUNDESLIGA_STATS_DEBUG'))

        def norm_label(label: str) -> str:
            lbl = label.strip().lower()
            lbl = re.sub(r'\((?:km|%)\)', '', lbl)
            lbl = lbl.replace('%', ' pct ')
            lbl = re.sub(r'[^a-z0-9]+', '_', lbl)
            lbl = re.sub(r'_+', '_', lbl).strip('_')
            return lbl

        def parse_number(val: str) -> Any:
            raw = val.strip()
            if raw.endswith('%'):
                num = raw.rstrip('%').strip()
                try:
                    return float(num)
                except ValueError:
                    return raw
            # distance (km)
            km_match = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s*km$', raw, re.I)
            if km_match:
                try:
                    return float(km_match.group(1))
                except ValueError:
                    return raw
            # plain int
            if re.match(r'^-?\d+$', raw):
                try:
                    return int(raw)
                except ValueError:
                    return raw
            # float
            if re.match(r'^-?\d+\.\d+$', raw):
                try:
                    return float(raw)
                except ValueError:
                    return raw
            return raw

        # Legacy simple table extraction remains (fallback)
        for row in soup.select('section table tr'):
            cells = row.find_all(['td','th'])
            if len(cells) == 2:
                k = norm_label(cells[0].get_text(strip=True))
                v_text = cells[1].get_text(strip=True)
                if k and v_text and k not in stats:
                    stats[k] = parse_number(v_text)

        if not stats_section:
            return stats

        # Season heading
        heading = stats_section.select_one('h3')
        if heading:
            season_txt = heading.get_text(' ', strip=True)
            if season_txt:
                stats['season_heading'] = season_txt

        # Stat boxes (grids)
        for box in stats_section.select('.stat-box'):
            label_el = box.select_one('.label')
            value_el = box.select_one('.value')
            if not label_el or not value_el:
                continue
            lab = norm_label(label_el.get_text(strip=True))
            val_text = value_el.get_text(strip=True)
            if lab and val_text and lab not in stats:
                stats[lab] = parse_number(val_text)

        # Key/value rows on right side (elementContainer)
        for row in stats_section.select('.elementContainer .row.element'):
            key_el = row.select_one('.key')
            val_el = row.select_one('.value')
            if not key_el or not val_el:
                continue
            lab = norm_label(key_el.get_text(strip=True))
            val_text = val_el.get_text(strip=True)
            if lab and val_text and lab not in stats:
                stats[lab] = parse_number(val_text)

        if debug:
            logger.info("Extracted %d stats keys", len(stats))
        return stats

    def _extract_profile_info(self, soup: BeautifulSoup) -> dict[str, Any]:
        profile: dict[str, Any] = {}
        for dl in soup.select('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            if len(dts) == len(dds) and dts:
                for dt, dd in zip(dts, dds):
                    k = dt.get_text(strip=True).lower().rstrip(':')
                    v = dd.get_text(strip=True)
                    if k and v:
                        profile[k] = v
        return profile

    # -------------------- JSON Fallbacks (LD-JSON / Hydration) --------------------
    def _extract_profile_from_ldjson(self, soup: BeautifulSoup) -> dict[str, Any]:
        out: dict[str, Any] = {}
        def set_if_absent(key: str, value: Any):
            if value is None:
                return
            if key not in out and value != '':
                out[key] = value
        for s in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(s.string or '{}')
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if not isinstance(obj, dict):
                    continue
                if obj.get('@type') in ('Organization','SportsTeam'):
                    # full name
                    name = obj.get('name')
                    set_if_absent('full_name', name)
                    # founded
                    founding = obj.get('foundingDate') or obj.get('foundingDateTime')
                    if isinstance(founding, str):
                        m = re.search(r'(\d{4})', founding)
                        if m:
                            try:
                                set_if_absent('founded', int(m.group(1)))
                            except Exception:
                                set_if_absent('founded', m.group(1))
                    # website/email/phone
                    set_if_absent('website', obj.get('url'))
                    set_if_absent('email', obj.get('email'))
                    set_if_absent('phone', obj.get('telephone'))
                    # address
                    addr = obj.get('address')
                    if isinstance(addr, dict):
                        street = addr.get('streetAddress')
                        city = addr.get('postalCode')
                        locality = addr.get('addressLocality')
                        if locality:
                            city = f"{addr.get('postalCode','')} {locality}".strip()
                        set_if_absent('street', street)
                        if city:
                            set_if_absent('city', city)
                        if street and city:
                            set_if_absent('address', f"{street}, {city}")
        return out

    def _extract_profile_from_hydration(self, html: str) -> dict[str, Any]:
        # Try to capture window.__NUXT__ hydration and mine for likely profile fields
        out: dict[str, Any] = {}
        data: Optional[dict] = None
        # Robust extraction: scan <script> tags and extract JSON after 'window.__NUXT__ ='
        try:
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script')
            for s in scripts:
                text = s.string or s.get_text() or ''
                if 'window.__NUXT__' not in text:
                    continue
                # Locate the first '{' after the assignment
                eq_idx = text.find('=')
                brace_idx = text.find('{', eq_idx if eq_idx != -1 else 0)
                if brace_idx == -1:
                    continue
                # Scan to find the matching closing '}' using a simple stack
                depth = 0
                end_idx = -1
                for i in range(brace_idx, len(text)):
                    ch = text[i]
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i
                            break
                if end_idx == -1:
                    continue
                json_str = text[brace_idx : end_idx + 1]
                try:
                    data = json.loads(json_str)
                    break
                except Exception:
                    continue
        except Exception:
            data = None
        if data is None:
            return out

        wanted_keys = {
            'full_name': {'full name','fullname','full_name','officialname','official_name','namelong','name_long'},
            'founded': {'founded','foundationyear','foundingdate','founding_date'},
            'street': {'street','streetaddress','address1','address_line1'},
            'city': {'city','addresslocality','location','town'},
            'phone': {'phone','telephone','tel'},
            'fax': {'fax','faxnumber'},
            'email': {'email'},
            'website': {'website','url','homepage'}
        }

        def norm(s: str) -> str:
            return re.sub(r'[^a-z0-9]+','', s.lower())

        def walker(obj):
            if isinstance(obj, dict):
                # Address dict special-case
                if {'streetAddress','addressLocality','postalCode'} & set(obj.keys()):
                    street = obj.get('streetAddress')
                    locality = obj.get('addressLocality')
                    pc = obj.get('postalCode')
                    city = f"{pc} {locality}".strip() if locality or pc else None
                    if street:
                        out.setdefault('street', street)
                    if city:
                        out.setdefault('city', city)
                    if street and city:
                        out.setdefault('address', f"{street}, {city}")
                # Bundesliga contact dict special-case
                if 'contact' in obj and isinstance(obj.get('contact'), dict):
                    c = obj.get('contact') or {}
                    try:
                        street = c.get('street')
                        house_no = c.get('houseNumber')
                        if street and house_no:
                            street_full = f"{street} {house_no}".strip()
                        else:
                            street_full = street or None
                        pc = c.get('postalCode')
                        city_name = c.get('city')
                        city_full = f"{pc} {city_name}".strip() if pc or city_name else None
                        if street_full:
                            out.setdefault('street', street_full)
                        if city_full:
                            out.setdefault('city', city_full)
                        if street_full and city_full:
                            out.setdefault('address', f"{street_full}, {city_full}")
                        phone = c.get('phone')
                        fax = c.get('fax')
                        email = c.get('email')
                        homepage = c.get('homepage')
                        def _norm_url(u: Any) -> Optional[str]:
                            if not isinstance(u, str):
                                return None
                            u = u.strip()
                            if not u:
                                return None
                            if not re.match(r'^https?://', u):
                                return f"https://{u}"
                            return u
                        if phone:
                            out.setdefault('phone', phone)
                        if fax:
                            out.setdefault('fax', fax)
                        if email:
                            out.setdefault('email', email)
                        if homepage:
                            out.setdefault('website', _norm_url(homepage))
                    except Exception:
                        pass
                # Colors dict special-case -> collect hexes
                if 'colors' in obj and isinstance(obj.get('colors'), dict):
                    colors = obj.get('colors') or {}
                    hexes: list[str] = []
                    try:
                        club = colors.get('club') or {}
                        for key in ('primary','secondary','primaryText','secondaryText'):
                            hexval = ((club.get(key) or {}).get('hex')) if isinstance(club.get(key), dict) else None
                            if isinstance(hexval, str) and hexval.startswith('#'):
                                hexes.append(hexval.upper())
                        jersey = colors.get('jersey') or {}
                        for variant in ('home','away','alternative'):
                            vobj = jersey.get(variant) or {}
                            for key in ('primary','secondary','number'):
                                hexval = ((vobj.get(key) or {}).get('hex')) if isinstance(vobj.get(key), dict) else None
                                if isinstance(hexval, str) and hexval.startswith('#'):
                                    hexes.append(hexval.upper())
                    except Exception:
                        pass
                    if hexes and 'club_colors' not in out:
                        # keep unique, preserve order
                        seen = set()
                        uniq = [h for h in hexes if not (h in seen or seen.add(h))]
                        out['club_colors'] = uniq
                # Stadium dict special-case
                if 'stadium' in obj and isinstance(obj.get('stadium'), dict):
                    st = obj.get('stadium') or {}
                    name = st.get('name')
                    cap = st.get('capacity')
                    if isinstance(name, str) and name and 'stadium' not in out:
                        out['stadium'] = name.strip()
                    if isinstance(cap, str) and cap and 'capacity' not in out:
                        cleaned = re.sub(r'[\u2009\u00a0]', ' ', cap)
                        digits = re.sub(r'[^0-9]', '', cleaned)
                        out['capacity'] = digits or cap.strip()
                for k, v in obj.items():
                    kn = norm(str(k))
                    for target, aliases in wanted_keys.items():
                        if kn in aliases and target not in out and isinstance(v, (str, int)):
                            if target == 'founded' and isinstance(v, str):
                                yr = re.search(r'(\d{4})', v)
                                out[target] = int(yr.group(1)) if yr else v
                            else:
                                out[target] = v
                    walker(v)
            elif isinstance(obj, list):
                for it in obj:
                    walker(it)

        walker(data)
        return out


# -------------------- Simple CLI Runner --------------------
async def _run_once(save_html: bool = False):
    try:
        from src.database.manager import DatabaseManager  # type: ignore
    except ImportError:
        # Fallback: minimal stub if DB layer not available
        class DummyDB:
            async def bulk_insert(self, *a, **kw):
                return None
        DatabaseManager = DummyDB  # type: ignore
    db = DatabaseManager()
    scraper = BundesligaClubScraper(db_manager=db, save_html=save_html)
    await scraper.initialize()
    try:
        data = await scraper.scrape_data()
        print(json.dumps({"count": len(data), "sample": data[:2]}, ensure_ascii=False))
    finally:
        await scraper.cleanup()


if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser(description="Bundesliga club scraper")
    p.add_argument('--save-html', action='store_true')
    args = p.parse_args()
    # On Windows: use Proactor loop when Playwright is enabled, otherwise Selector (legacy compatibility)
    if sys.platform.startswith('win'):
        use_pw = os.getenv("BUNDESLIGA_USE_PLAYWRIGHT", "0") in ("1", "true", "True")
        if use_pw and hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        elif hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run_once(save_html=args.save_html))
