"""
Courtside1891 Scraper for basketball fixtures, teams, and competitions
"""

import asyncio
import csv
import json
import os
from datetime import datetime

from playwright.async_api import Page, async_playwright

from src.core.config import Settings
from src.data_collection.scrapers.base import BaseScraper, ScrapingConfig
from src.common.playwright_utils import (
    accept_consent,
    infinite_scroll,
    extract_next_data,
    parse_captured_json,
    extract_from_ld_json,
    normalize_game_node,
)
from src.domain.contracts import Fixture
from src.database.manager import DatabaseManager


class CourtsideScraper(BaseScraper):
    """Scraper for Courtside1891 basketball fixtures and team IDs"""

    def __init__(self, db_manager: DatabaseManager, settings: Settings):
        cfg = ScrapingConfig(
            base_url="https://www.courtside1891.basketball",
            selectors={
                # Updated selectors based on common patterns
                "fixtures_container": ".MuiContainer-root, [class*='fixture-container'], [class*='games-container']",
                "fixture_rows": ".MuiCard-root, [class*='fixture-card'], [class*='game-card'], [data-testid*='fixture']",
                "competition_name": "[class*='competition'], [class*='league'], [data-testid*='competition']",
                "home_team": "[class*='home-team'], [class*='team1'], [data-testid*='home']",
                "away_team": "[class*='away-team'], [class*='team2'], [data-testid*='away']",
                "score": "[class*='score'], [class*='result'], [data-testid*='score']",
                "team_id_attr": "data-team-id, data-id, data-team",
                "fixture_id_attr": "data-fixture-id, data-id, data-game",
                "competition_id_attr": "data-competition-id, data-league, data-tournament",
            },
            headers=None,
            delay_range=(5, 10),
            max_retries=5,
            timeout=120,
            # Disable proxies for reliability in no-DB terminal test
            use_proxy=False,
            proxy_list=None,
            anti_detection=True,
            screenshot_on_error=True,
        )
        super().__init__(cfg, db_manager, name="courtside1891")
        self.settings = settings

    async def scrape_data(self) -> list[dict]:
        """Scrape with comprehensive error handling"""
        async with async_playwright() as p:
            # Run non-headless to improve reliability with consent and lazy-loading UIs
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1366, "height": 768},
            )
            page = await context.new_page()

            try:
                captured_json: list[dict] = []  # network JSON payloads

                async def _on_response(resp):
                    try:
                        ctype = (resp.headers.get("content-type") or "").lower()
                        url = resp.url.lower()
                        if "application/json" in ctype and any(
                            k in url for k in ["fixture", "game", "match", "schedule"]
                        ):
                            data = await resp.json()
                            captured_json.append({"url": resp.url, "data": data})
                    except Exception:
                        pass

                page.on("response", _on_response)
                # Load page with multiple wait conditions
                self.logger.info("Loading Courtside1891 website")
                try:
                    await page.goto(
                        "https://www.courtside1891.basketball/games",
                        timeout=180000,  # Increased timeout to 3 minutes
                        wait_until="domcontentloaded",  # Changed from networkidle to domcontentloaded
                    )
                    self.logger.info("Page loaded successfully")
                except Exception as e:
                    self.logger.error(f"Error loading page: {str(e)}")
                    # Try to continue even if load times out
                    pass
                # Handle cookie/consent banner if present
                await accept_consent(page)

                # Add console message handler to capture browser logs
                def console_handler(msg):
                    self.logger.debug(f"BROWSER CONSOLE: {msg.type}: {msg.text}")

                page.on("console", console_handler)
                # Small settle delay with error handling
                try:
                    await page.wait_for_timeout(3000)  # Increased initial delay

                    # Try to handle any modals or popups
                    await accept_consent(page)

                    # Infinite scroll with better error handling
                    await infinite_scroll(
                        page, max_time_ms=60000, idle_rounds=3
                    )  # Increased timeout
                except Exception as e:
                    self.logger.warning(f"Error during page interaction: {str(e)}")
                    # Continue with whatever content we have

                # Wait for content (polling across alternative selectors)
                self.logger.info("Waiting for fixtures (polling up to 60s)")
                found = False
                selectors = [
                    '[data-testid="fixture-row"]',
                    '[data-testid*="fixture"]',
                    'a[href*="/game/"]',
                ]
                for i in range(60):  # ~60s
                    counts = []
                    for sel in selectors:
                        try:
                            cnt = await page.evaluate(
                                "selector => document.querySelectorAll(selector).length",
                                sel,
                            )
                        except Exception:
                            cnt = 0
                        counts.append((sel, cnt))
                    total = sum(c for _, c in counts)
                    if total > 0:
                        self.logger.info(f"Fixture candidates detected: {counts}")
                        found = True
                        break
                    await page.wait_for_timeout(1000)
                if not found:
                    self.logger.warning("No fixture elements detected after polling")
                    # Try extracting from Next.js data as fallback
                    next_data_fixtures = await extract_next_data(page)
                    if next_data_fixtures:
                        self.logger.info(
                            f"Extracted {len(next_data_fixtures)} items from __NEXT_DATA__"
                        )
                        return next_data_fixtures
                    # Try network-captured JSON responses
                    if captured_json:
                        parsed = parse_captured_json(captured_json)
                        if parsed:
                            self.logger.info(f"Extracted {len(parsed)} items from network JSON")
                            return parsed

                # Debug: Log page HTML structure
                page_html = await page.content()
                self.logger.debug(f"Page HTML (first 2000 chars): {page_html[:2000]}")

                # Debug: Log all elements with data-testid
                test_ids = await page.evaluate(
                    """() => {
                    return Array.from(document.querySelectorAll('[data-testid]'))
                        .map(el => ({
                            tag: el.tagName,
                            testid: el.getAttribute('data-testid'),
                            text: el.textContent.trim().replace(/\s+/g, ' ').substring(0, 50) + '...',
                            id: el.id || null,
                            class: el.className || null
                        }));
                }"""
                )
                self.logger.info(f"Found {len(test_ids)} elements with data-testid:")
                for item in test_ids[:20]:  # Log first 20 to avoid too much output
                    testid = item.get("testid", "N/A")
                    tag = item.get("tag", "?")
                    text = item.get("text", "")
                    self.logger.info(f"  - {tag} [data-testid='{testid}']: {text}")

                # Extract data
                self.logger.info("Extracting fixture data")
                fixtures = await page.evaluate(
                    """() => {
                    // Try multiple selector patterns
                    const selectors = [
                        '[data-testid="fixture-row"]',
                        '.fixture-row',
                        '.game-row',
                        'div[class*="fixture"]',
                        'div[class*="game"]',
                        'a[href*="/game/"]',
                        'a[href*="/fixture/"]'
                    ];
                    
                    // Try each selector until we find matches
                    let rows = [];
                    for (const sel of selectors) {
                        rows = Array.from(document.querySelectorAll(sel));
                        if (rows.length > 0) {
                            console.log(`Found ${rows.length} rows with selector: ${sel}`);
                            break;
                        }
                    }
                    
                    if (rows.length === 0) {
                        console.error('No fixture rows found with any selector');
                        return [];
                    }
                    
                    const parseScore = (s) => {
                        if (!s) return { home_score: null, away_score: null };
                        const t = s.trim();
                        const parts = t.replace(/\s+/g,'').replace(':','-').split('-');
                        const toInt = (x) => { const n = parseInt(x, 10); return Number.isFinite(n) ? n : null; };
                        return { home_score: toInt(parts[0]), away_score: toInt(parts[1]) };
                    };
                    return rows.map(row => {
                        try {
                            const homeEl = row.querySelector('[data-testid="team-home"]');
                            const awayEl = row.querySelector('[data-testid="team-away"]');
                            const scoreEl = row.querySelector('[data-testid="fixture-score"]');
                            const statusEl = row.querySelector('[data-testid*="status"], [data-testid*="time"], time, .status');
                            const linkEl = row.querySelector('a[href*="/game/"]');
                            const compWrap = row.closest('[data-testid="competition-fixtures"]');
                            const compNameEl = compWrap?.querySelector('[data-testid="competition-name"]');
                            const { home_score, away_score } = parseScore(scoreEl?.textContent || '');

                            const getId = (el) => {
                                if (!el) return null;
                                // common id attributes seen in markup
                                return el.getAttribute('data-team-id') || el.getAttribute('data-id') || el.getAttribute('data-external-id') || null;
                            };
                            const compId = compWrap?.getAttribute('data-competition-id') || compWrap?.getAttribute('data-id') || null;
                            const rawHref = linkEl?.getAttribute('href') || null;
                            const cleanHref = rawHref ? rawHref.split('?')[0] : null;

                            return {
                                id: row.dataset.fixtureId || row.getAttribute('data-fixture-id') || cleanHref,
                                home: homeEl?.textContent?.trim() || null,
                                away: awayEl?.textContent?.trim() || null,
                                home_id: getId(homeEl),
                                away_id: getId(awayEl),
                                home_score,
                                away_score,
                                status: statusEl?.textContent?.trim() || null,
                                competition: compNameEl?.textContent?.trim() || null,
                                competition_id: compId,
                                timestamp: new Date().toISOString(),
                                url: cleanHref,
                            };
                        } catch (e) {
                            return null;
                        }
                    }).filter(Boolean);
                }"""
                )

                # Log the raw fixtures data for debugging
                self.logger.info(f"Extracted {len(fixtures) if fixtures else 0} fixtures")
                if fixtures:
                    self.logger.debug(
                        f"Sample fixture data: {json.dumps(fixtures[0], indent=2) if fixtures[0] else 'No data'}"
                    )

                # Fallback extraction using broader anchors if needed
                if not fixtures:
                    anchors_guess = await page.evaluate(
                        """(origin) => {
                        const anchors = Array.from(document.querySelectorAll('a[href*="/game/"]'));
                        const abs = (href) => href?.startsWith('http') ? href : `${origin}${href}`;
                        return anchors.map(a => ({
                            id: (a.getAttribute('href')||'').split('?')[0],
                            url: abs((a.getAttribute('href')||'').split('?')[0]),
                            text: (a.textContent || '').replace(/\s+/g,' ').trim() || null,
                            timestamp: new Date().toISOString(),
                        }));
                    }""",
                        self.config.base_url.rstrip("/"),
                    )
                    fixtures = anchors_guess
                if not fixtures and captured_json:
                    parsed = parse_captured_json(captured_json)
                    if parsed:
                        fixtures = parsed
                # As a last resort, return the list of JSON endpoints observed for manual inspection
                if not fixtures and captured_json:
                    fixtures = [
                        {
                            "id": None,
                            "home": None,
                            "away": None,
                            "score": None,
                            "timestamp": datetime.utcnow().isoformat(),
                            "debug_json_url": item.get("url"),
                        }
                        for item in captured_json[:10]
                    ]

                # Enrich if fixtures look incomplete (missing names/ids/scores)
                def is_incomplete(item: dict) -> bool:
                    keys = item.keys()
                    return not (
                        ("home" in keys or "home_id" in keys)
                        and ("away" in keys or "away_id" in keys)
                        and ("home_score" in keys or "away_score" in keys)
                    )

                if fixtures and any(is_incomplete(f) for f in fixtures):
                    # Collect game anchors from page and enrich
                    self.logger.info(
                        "Results look incomplete, collecting game links for enrichment..."
                    )
                    game_links = await page.evaluate(
                        """(origin) => {
                        const anchors = Array.from(document.querySelectorAll('a[href*="/game/"]'));
                        const seen = new Set();
                        const abs = (href) => href?.startsWith('http') ? href : `${origin}${href}`;
                        return anchors.map(a => a.getAttribute('href')).filter(Boolean).filter(h => {
                            if (seen.has(h)) return false; seen.add(h); return true;
                        }).map(href => ({ id: href.split('?')[0], url: abs(href.split('?')[0]) }));
                    }""",
                        self.config.base_url.rstrip("/"),
                    )
                    if game_links:
                        enriched = await self._enrich_from_game_pages(context, game_links)
                        if enriched:
                            fixtures = enriched

                # Unify record shape before returning
                unified = self._unify_fixture_records(fixtures)
                missing_counts = {
                    "fixture_id": sum(1 for f in unified if not f.get("fixture_id")),
                    "home_team_id": sum(1 for f in unified if not f.get("home_team_id")),
                    "away_team_id": sum(1 for f in unified if not f.get("away_team_id")),
                    "competition_id": sum(1 for f in unified if not f.get("competition_id")),
                }
                self.logger.info(
                    f"Unified {len(unified)} fixtures. Missing fields: {missing_counts}"
                )

                self.logger.info(f"Successfully scraped {len(unified)} fixtures")
                # Map unified dicts to Fixture DTOs
                fixtures_dto = [
                    Fixture(
                        fixture_id=f.get("fixture_id"),
                        home_team_name=f.get("home_team_name"),
                        away_team_name=f.get("away_team_name"),
                        home_team_id=f.get("home_team_id"),
                        away_team_id=f.get("away_team_id"),
                        competition_name=f.get("competition_name"),
                        competition_id=f.get("competition_id"),
                        home_score=f.get("home_score"),
                        away_score=f.get("away_score"),
                        status=f.get("status"),
                        url=f.get("url"),
                        scraped_at=datetime.fromisoformat(f.get("timestamp")) if f.get("timestamp") else datetime.utcnow(),
                    )
                    for f in unified
                ]
                return fixtures_dto

            except Exception as e:
                self.logger.error(f"Scraping failed: {str(e)}", exc_info=True)
                # Save error screenshot to logs/courtside with timestamp
                ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                out_dir = os.path.join(self.settings.log_file_path, "courtside")
                try:
                    os.makedirs(out_dir, exist_ok=True)
                    screenshot_path = os.path.join(out_dir, f"courtside_error_{ts}.png")
                    await page.screenshot(path=screenshot_path)
                    self.logger.info(f"Saved error screenshot: {screenshot_path}")
                except Exception as se:
                    self.logger.warning(f"Failed to save error screenshot: {se}")
                return []

            finally:
                await browser.close()

    async def _extract_from_next_data(self, page: Page) -> list[dict]:
        """Delegate to shared utils.extract_next_data"""
        return await extract_next_data(page)

    async def _enrich_from_game_pages(self, context, anchors: list[dict]) -> list[dict]:
        """Visit each game page to extract full details using JSON normalization. Limits concurrency for stability."""
        sem = asyncio.Semaphore(4)
        base = self.config.base_url.rstrip("/")

        async def worker(item):
            href = str(item.get("id") or "")
            if not href:
                return None
            url = href if href.startswith("http") else f"{base}{href}"
            async with sem:
                return await self._enrich_single_game(context, url)

        tasks = [asyncio.create_task(worker(a)) for a in anchors]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        enriched: list[dict] = []
        for r in results:
            if isinstance(r, dict) and r:
                enriched.append(r)
        return enriched

    async def _enrich_single_game(self, context, url: str) -> dict:
        """Open a game page and extract normalized details via __NEXT_DATA__ or network JSON."""
        page = await context.new_page()
        try:
            captured_json: list[dict] = []

            async def _on_response(resp):
                try:
                    ctype = (resp.headers.get("content-type") or "").lower()
                    if "application/json" in ctype:
                        data = await resp.json()
                        captured_json.append({"url": resp.url, "data": data})
                except Exception:
                    pass

            page.on("response", _on_response)

            await page.goto(url, timeout=120000, wait_until="networkidle")
            await accept_consent(page)
            await page.wait_for_timeout(500)

            # Try __NEXT_DATA__ first
            next_items = await extract_next_data(page)
            if next_items:
                # Choose the first that has both teams
                for it in next_items:
                    if (it.get("home") or it.get("home_id")) and (
                        it.get("away") or it.get("away_id")
                    ):
                        return it

            # Then try network JSON
            parsed = parse_captured_json(captured_json)
            if parsed:
                for it in parsed:
                    if (it.get("home") or it.get("home_id")) and (
                        it.get("away") or it.get("away_id")
                    ):
                        return it

            # Finally, try direct DOM extraction on the game page
            try:
                dom_item = await page.evaluate(
                    """() => {
                    const sel = (s) => document.querySelector(s);
                    const text = (el) => (el && el.textContent ? el.textContent.trim() : null);
                    const getId = (el) => {
                        if (!el) return null;
                        return el.getAttribute('data-team-id') || el.getAttribute('data-id') || el.getAttribute('data-external-id') || null;
                    };
                    const parseScore = (s) => {
                        if (!s) return { home_score: null, away_score: null };
                        const t = s.trim();
                        const parts = t.replace(/\s+/g,'').replace(':','-').split('-');
                        const toInt = (x) => { const n = parseInt(x, 10); return Number.isFinite(n) ? n : null; };
                        return { home_score: toInt(parts[0]), away_score: toInt(parts[1]) };
                    };
                    // Common data-testids on game detail pages
                    const homeEl = sel('[data-testid="team-home"], [data-testid*="home"]');
                    const awayEl = sel('[data-testid="team-away"], [data-testid*="away"]');
                    const scoreEl = sel('[data-testid="fixture-score"], [data-testid*="score"], .score');
                    const statusEl = sel('[data-testid*="status"], [data-testid*="time"], time, .status');
                    const compWrap = sel('[data-testid="competition-fixtures"], [data-testid*="competition"], [class*="competition"]');
                    const compNameEl = compWrap ? compWrap.querySelector('[data-testid="competition-name"], [class*="competition-name"]') : null;
                    const { home_score, away_score } = parseScore(text(scoreEl) || '');
                    const linkEl = sel('a[href*="/game/"]');
                    const rawHref = linkEl ? linkEl.getAttribute('href') : (window.location ? window.location.pathname : null);
                    const cleanHref = rawHref ? rawHref.split('?')[0] : null;
                    const compId = compWrap ? (compWrap.getAttribute('data-competition-id') || compWrap.getAttribute('data-id') || null) : null;

                    const res = {
                        id: cleanHref,
                        home: text(homeEl),
                        away: text(awayEl),
                        home_id: getId(homeEl),
                        away_id: getId(awayEl),
                        home_score,
                        away_score,
                        status: text(statusEl),
                        competition: text(compNameEl),
                        competition_id: compId,
                        timestamp: new Date().toISOString(),
                        url: cleanHref,
                    };
                    const hasTeams = (res.home || res.home_id) && (res.away || res.away_id);
                    return hasTeams ? res : null;
                }"""
                )
                if dom_item:
                    return dom_item
            except Exception:
                pass

            # Finally, try schema.org LD+JSON on the page
            ld_list = await page.evaluate(
                """() => {
                const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
                return scripts.map(s => s.textContent).filter(Boolean);
            }"""
            )
            if ld_list:
                ld_item = extract_from_ld_json(ld_list)
                if ld_item:
                    return ld_item

            return {"id": url, "timestamp": datetime.utcnow().isoformat()}
        except Exception:
            return {"id": url, "timestamp": datetime.utcnow().isoformat()}
        finally:
            await page.close()

    def _extract_from_ld_json(self, json_texts: list[str]) -> dict:
        """Delegate to shared utils.extract_from_ld_json"""
        return extract_from_ld_json(json_texts)

    async def _try_handle_consent(self, page: Page) -> None:
        """Delegate to shared utils.accept_consent"""
        await accept_consent(page)

    def _extract_from_captured_json(self, captured_json: list[dict]) -> list[dict]:
        """Delegate to shared utils.parse_captured_json"""
        return parse_captured_json(captured_json)

    def _normalize_game_node(self, node: dict) -> dict:
        """Delegate to shared utils.normalize_game_node"""
        return normalize_game_node(node)

    def _unify_fixture_records(self, items: list[dict]) -> list[dict]:
        """Convert a list of mixed-shape records (DOM/Next.js/JSON) to unified fixture dicts.
        Output keys: fixture_id, competition_id, competition_name, home_team_id, away_team_id,
        home_team_name, away_team_name, score, url, timestamp.
        """

        def to_score(home_score, away_score):
            try:
                if home_score is None or away_score is None:
                    return None
                return f"{int(home_score)}-{int(away_score)}"
            except Exception:
                return None

        unified: list[dict] = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            # Accept both DOM-shape and normalized-shape keys
            fixture_id = it.get("fixture_id") or it.get("id") or it.get("url")
            competition_id = it.get("competition_id")
            competition_name = it.get("competition_name") or it.get("competition")
            home_team_id = it.get("home_team_id") or it.get("home_id")
            away_team_id = it.get("away_team_id") or it.get("away_id")
            home_team_name = it.get("home_team_name") or it.get("home")
            away_team_name = it.get("away_team_name") or it.get("away")
            score = it.get("score")
            if not score:
                score = to_score(it.get("home_score"), it.get("away_score"))
            url = it.get("url") or None
            timestamp = it.get("timestamp") or datetime.utcnow().isoformat()

            unified.append(
                {
                    "fixture_id": fixture_id,
                    "competition_id": competition_id,
                    "competition_name": competition_name,
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "home_team_name": home_team_name,
                    "away_team_name": away_team_name,
                    "score": score,
                    "url": url,
                    "timestamp": timestamp,
                }
            )
        return unified

    async def _extract_fixtures(self, page: Page) -> list[dict]:
        """Extract fixture data from the page with improved error handling and debugging"""
        self.logger.info("Starting enhanced fixture extraction...")

        # Take a screenshot for debugging
        await page.screenshot(path="debug_page.png", full_page=True)

        # First, try to get the page content as text for debugging
        try:
            content = await page.content()
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            self.logger.info("Saved page content to debug_page.html")
        except Exception as e:
            self.logger.warning(f"Could not save page content: {str(e)}")

        # Try multiple selectors to find fixture containers

        # Wait for any potential dynamic content
        try:
            # Try to wait for common loading indicators to disappear
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)  # Additional wait for any remaining JS

            # Check if we have any content
            content_check = await page.evaluate(
                """() => {
                return {
                    bodyText: document.body.innerText.length,
                    hasFixtures: document.querySelectorAll('[class*="fixture"], [class*="game"]').length > 0,
                    hasData: document.querySelectorAll('[data-testid]').length > 0
                };
            }"""
            )

            self.logger.info(f"Content check: {content_check}")

        except Exception as e:
            self.logger.warning(f"Error during content check: {str(e)}")

        # Extract fixtures with enhanced debugging
        return await page.evaluate(
            """(selectors) => {
            const fixtures = [];
            
            // First, log all data-testid attributes for debugging
            const allTestIds = Array.from(document.querySelectorAll('[data-testid]'));
            console.log(`Found ${allTestIds.length} elements with data-testid`);
            allTestIds.slice(0, 10).forEach((el, i) => {
                console.log(`  ${i+1}. [${el.tagName}] data-testid="${el.getAttribute('data-testid')}"`);
            });
            
            // Try multiple selector patterns for rows with more specific patterns
            const rowSelectors = [
                // Common patterns in modern web apps
                '[data-testid*="fixture"]',
                '[data-testid*="game"]',
                '.MuiCard-root',
                
                // Common class patterns
                '[class*="fixture" i]',
                '[class*="game" i]',
                '[class*="match" i]',
                
                // Common semantic elements
                'article',
                'section',
                'div[role="listitem"]',
                'div[role="article"]',
                
                // More generic selectors as fallback
                'div > div > div',  // Common in grid layouts
                'a[href*="/game/"]', // Direct game links
                'a[href*="/fixture/"]'
            ];
            
            // Try to find the best matching selector
            let rows = [];
            for (const sel of rowSelectors) {
                try {
                    const matches = document.querySelectorAll(sel);
                    if (matches.length > 3) {  // Only consider if we find multiple matches
                        console.log(`Found ${matches.length} potential rows with selector: ${sel}`);
                        rows = Array.from(matches);
                        break;
                    }
                } catch (e) {
                    console.error(`Error with selector ${sel}:`, e);
                }
            }
            
            if (rows.length === 0) {
                // If no rows found with selectors, try to find any clickable elements that might be fixtures
                console.warn('No fixture rows found with standard selectors, trying fallback...');
                
                // Look for any clickable elements that might be fixtures
                const potentialFixtures = Array.from(document.querySelectorAll('a, button, [role="button"]'))
                    .filter(el => {
                        const text = (el.textContent || '').toLowerCase();
                        return text.includes('vs') || 
                               text.includes('vs.') ||
                               (el.querySelector('div') && el.querySelector('div').textContent.includes('vs'));
                    });
                
                if (potentialFixtures.length > 0) {
                    console.log(`Found ${potentialFixtures.length} potential fixtures by content`);
                    rows = potentialFixtures;
                } else {
                    console.error('No fixture rows found with any selector');
                    
                    // As a last resort, return the entire page structure for debugging
                    console.log('Page structure for debugging:');
                    console.log(document.documentElement.outerHTML.substring(0, 1000) + '...');
                    
                    return [];
                }
            }
            
            rows.forEach((row, index) => {
                try {
                    console.log(`\n--- Processing row ${index + 1}/${rows.length} ---`);
                    
                    // Log the row HTML for debugging
                    const rowHtml = row.outerHTML.substring(0, 200) + (row.outerHTML.length > 200 ? '...' : '');
                    console.log(`Row HTML: ${rowHtml}`);
                    
                    // Try multiple selector patterns for each field with better debugging
                    const getFirstMatch = (selectors, parent = row) => {
                        if (!parent) return null;
                        
                        const selectorList = typeof selectors === 'string' ? 
                            selectors.split(',').map(s => s.trim()) : 
                            Array.isArray(selectors) ? selectors : [selectors];
                            
                        for (const sel of selectorList) {
                            try {
                                const el = parent.querySelector(sel);
                                if (el) {
                                    console.log(`Found match for selector '${sel}':`, 
                                        el.textContent.trim().substring(0, 50));
                                    return el;
                                }
                            } catch (e) {
                                console.warn(`Error with selector '${sel}':`, e);
                            }
                        }
                        console.log(`No match found for selectors: ${selectorList.join(', ')}`);
                        return null;
                    };
                    
                    // Enhanced attribute getter with better debugging
                    const getAttr = (el, attrNames, parent = null) => {
                        if (!el) {
                            console.log(`No element provided to getAttr for attributes: ${attrNames}`);
                            return null;
                        }
                        
                        const attrs = typeof attrNames === 'string' ? 
                            attrNames.split(',').map(a => a.trim()) : 
                            Array.isArray(attrNames) ? attrNames : [attrNames];
                            
                        // Try direct attributes first
                        for (const attr of attrs) {
                            try {
                                const value = el.getAttribute(attr);
                                if (value) {
                                    console.log(`Found attribute '${attr}': ${value}`);
                                    return value;
                                }
                            } catch (e) {
                                console.warn(`Error getting attribute '${attr}':`, e);
                            }
                        }
                        
                        // Try dataset if no direct attribute found
                        for (const attr of attrs) {
                            try {
                                const dataAttr = attr.startsWith('data-') ? 
                                    attr.substring(5).replace(/-([a-z])/g, (g) => g[1].toUpperCase()) : 
                                    attr;
                                if (el.dataset[dataAttr] !== undefined) {
                                    console.log(`Found dataset '${dataAttr}':`, el.dataset[dataAttr]);
                                    return el.dataset[dataAttr];
                                }
                            } catch (e) {
                                console.warn(`Error getting dataset '${attr}':`, e);
                            }
                        }
                        
                        // Try parent element if provided
                        if (parent && parent !== el) {
                            console.log(`Trying parent element for attributes: ${attrs.join(', ')}`);
                            return getAttr(parent, attrs);
                        }
                        
                        console.log(`No matching attributes found: ${attrs.join(', ')}`);
                        return null;
                    };
                    
                    // Try to find competition/league information
                    const competition = getFirstMatch([
                        selectors.competition_name,
                        '.competition-name',
                        '.league-name',
                        '.tournament-name',
                        '[class*="competition"]',
                        '[class*="league"]',
                        'h2, h3, h4'  // Fallback to any heading
                    ]);
                    
                    // Try to find teams and score in various ways
                    let homeTeam, awayTeam, score;
                    
                    // First try: Look for a container with both teams and score
                    const teamContainer = getFirstMatch([
                        '.match-teams',
                        '.fixture-teams',
                        '.game-teams',
                        '[class*="vs"]',
                        'div > div'  // Generic container
                    ]);
                    
                    if (teamContainer) {
                        console.log('Found team container, extracting teams...');
                        
                        // Try to find team elements within the container
                        const teams = teamContainer.querySelectorAll([
                            '[class*="team"]',
                            'div > div',  // Common pattern for team containers
                            'span, div, p' // Fallback to common text elements
                        ].join(','));
                        
                        if (teams.length >= 2) {
                            homeTeam = teams[0];
                            awayTeam = teams[1];
                            console.log(`Found teams in container: ${homeTeam.textContent.trim()} vs ${awayTeam.textContent.trim()}`);
                            
                            // Look for score near the teams
                            score = teamContainer.querySelector([
                                selectors.score,
                                '.score',
                                '.result',
                                'span, div'  // Fallback to any text element
                            ].join(','));
                        }
                    }
                    
                    // Second try: If no container found, try direct selectors
                    if (!homeTeam || !awayTeam) {
                        homeTeam = getFirstMatch([
                            selectors.home_team,
                            '.home-team',
                            '.team-1',
                            '[class*="home"]',
                            'div:first-child'  // First child as fallback
                        ]);
                        
                        awayTeam = getFirstMatch([
                            selectors.away_team,
                            '.away-team',
                            '.team-2',
                            '[class*="away"]',
                            'div:last-child'  // Last child as fallback
                        ]);
                        
                        score = getFirstMatch([
                            selectors.score,
                            '.score',
                            '.result',
                            'span, div'  // Fallback to any text element
                        ]);
                    }
                    
                    // Extract IDs from various possible locations
                    const homeTeamId = getAttr(homeTeam, [
                        selectors.team_id_attr,
                        'data-team',
                        'data-id',
                        'id'
                    ], row);
                    
                    const awayTeamId = getAttr(awayTeam, [
                        selectors.team_id_attr,
                        'data-team',
                        'data-id',
                        'id'
                    ], row);
                    
                    // Try multiple ways to get fixture ID
                    let fixtureId = getAttr(row, [
                        selectors.fixture_id_attr,
                        'data-fixture',
                        'data-game',
                        'data-id',
                        'id'
                    ]);
                    
                    // If no ID found in attributes, try to extract from URL
                    if (!fixtureId) {
                        const link = row.href || (row.querySelector('a[href*="/game/"], a[href*="/fixture/"]')?.href || '');
                        if (link) {
                            const idMatch = link.match(/(\d+)$/);
                            if (idMatch) {
                                fixtureId = idMatch[1];
                                console.log(`Extracted fixture ID from URL: ${fixtureId}`);
                            }
                        }
                    }
                    
                    // Get competition ID with fallbacks
                    const competitionId = getAttr(competition, [
                        selectors.competition_id_attr,
                        'data-competition',
                        'data-league',
                        'data-tournament',
                        'data-id',
                        'id'
                    ], row) || 'unknown';
                    
                    // Enhanced text cleaner with better handling of various element types
                    const cleanText = (el) => {
                        if (!el) {
                            console.log('No element provided to cleanText');
                            return null;
                        }
                        
                        // Handle different element types
                        let text = '';
                        if (typeof el === 'string') {
                            text = el;
                        } else if ('textContent' in el) {
                            text = el.textContent || '';
                        } else if ('innerText' in el) {
                            text = el.innerText || '';
                        } else if ('value' in el) {
                            text = el.value || '';
                        } else if (el.nodeType === Node.TEXT_NODE) {
                            text = el.nodeValue || '';
                        } else {
                            console.log('Unknown element type in cleanText:', el);
                            text = String(el);
                        }
                        
                        // Clean up the text
                        return text
                            .replace(/[\r\n\t]+/g, ' ')  // Replace newlines and tabs with spaces
                            .replace(/[\s\u00a0]+/g, ' ')  // Replace all whitespace with single space
                            .trim();
                    };
                    
                    // Try to find a link to the fixture details
                    let link = row.href || (row.querySelector('a[href*="/game/"], a[href*="/fixture/"]')?.href || '');
                    if (!link && row.closest) {
                        // Try to find a parent link
                        const parentLink = row.closest('a[href*="/game/"], a[href*="/fixture/"]');
                        if (parentLink) {
                            link = parentLink.href;
                        }
                    }
                    
                    // Build the fixture object with all available data
                    const fixture = {
                        id: fixtureId || `generated-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
                        competition: cleanText(competition) || 'Unknown Competition',
                        competition_id: competitionId,
                        home_team: cleanText(homeTeam) || 'Home Team',
                        home_team_id: homeTeamId || `home-${Date.now()}`,
                        away_team: cleanText(awayTeam) || 'Away Team',
                        away_team_id: awayTeamId || `away-${Date.now()}`,
                        score: cleanText(score) || '0 - 0',
                        url: link || null,
                        timestamp: new Date().toISOString(),
                        _debug: {
                            selector: rowSelectors.find(sel => row.matches(sel)) || 'unknown',
                            outerHTML: row.outerHTML.substring(0, 500) + (row.outerHTML.length > 500 ? '...' : ''),
                            parentHTML: row.parentElement ? 
                                row.parentElement.outerHTML.substring(0, 300) + 
                                (row.parentElement.outerHTML.length > 300 ? '...' : '') : 'No parent'
                        }
                    };
                    
                    // Log the extracted fixture for debugging
                    console.log('Extracted fixture:', JSON.stringify({
                        id: fixture.id,
                        competition: fixture.competition,
                        home_team: fixture.home_team,
                        away_team: fixture.away_team,
                        score: fixture.score
                    }, null, 2));
                    
                    // Only add if we have at least some data
                    if (fixture.id || fixture.home_team || fixture.away_team || fixture.competition) {
                        fixtures.push(fixture);
                    }
                } catch (e) {
                    console.error('Error processing row:', e);
                }
            });
            
            console.log(`Extracted ${fixtures.length} fixtures`);
            return fixtures;
        }""",
            self.config.selectors,
        )

        # Log extraction results
        self.logger.info(f"Extracted {len(fixtures)} fixtures")
        if fixtures:
            self.logger.debug(f"Sample fixture: {json.dumps(fixtures[0], indent=2)}")

            # Log any fixtures with null values for debugging
            null_fixtures = [f for f in fixtures if not (f.get("home_team") and f.get("away_team"))]
            if null_fixtures:
                self.logger.warning(f"Found {len(null_fixtures)} fixtures with missing team names")
                self.logger.debug(f"Sample null fixture: {json.dumps(null_fixtures[0], indent=2)}")

        return fixtures

    async def _process_fixtures(self, fixtures: list[dict]) -> list[dict]:
        """Filter and prepare fixtures for DB insertion"""
        if not fixtures:
            return []

        # Filter out fixtures already in DB
        fixture_ids = [f["fixture_id"] for f in fixtures]
        existing_fixture_ids: set = set()
        if fixture_ids:
            existing_fixtures = await self.db_manager.execute_query(
                """SELECT external_id FROM fixtures 
                WHERE external_id = ANY($1::text[])""",
                fixture_ids,
            )
            existing_fixture_ids = {row["external_id"] for row in existing_fixtures}

        # Filter out teams already in DB
        team_ids = list(
            {f["home_team_id"] for f in fixtures} | {f["away_team_id"] for f in fixtures}
        )
        existing_team_ids: set = set()
        if team_ids:
            existing_teams = await self.db_manager.execute_query(
                """SELECT external_id FROM teams 
                WHERE external_id = ANY($1::text[])""",
                team_ids,
            )
            existing_team_ids = {row["external_id"] for row in existing_teams}

        # Prepare data for insertion
        new_fixtures = []
        new_teams = set()

        for fixture in fixtures:
            if fixture["fixture_id"] not in existing_fixture_ids:
                new_fixtures.append(
                    {
                        "external_id": fixture["fixture_id"],
                        "competition_id": fixture["competition_id"],
                        "home_team_id": fixture["home_team_id"],
                        "away_team_id": fixture["away_team_id"],
                        "score": fixture["score"],
                    }
                )

            if fixture["home_team_id"] not in existing_team_ids:
                new_teams.add((fixture["home_team_id"], fixture["home_team_name"]))

            if fixture["away_team_id"] not in existing_team_ids:
                new_teams.add((fixture["away_team_id"], fixture["away_team_name"]))

        # Insert new data
        if new_teams:
            await self.db_manager.execute_many(
                """
                INSERT INTO teams (external_id, name, sport_type, created_at)
                VALUES ($1, $2, 'basketball', NOW())
                ON CONFLICT (external_id) DO NOTHING
                """,
                [(team_id, name) for team_id, name in new_teams],
            )

        if new_fixtures:
            await self.db_manager.execute_many(
                """
                INSERT INTO fixtures (external_id, competition_id, 
                                    home_team_id, away_team_id, score, created_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (external_id) DO NOTHING
                """,
                [
                    (
                        f["external_id"],
                        f["competition_id"],
                        f["home_team_id"],
                        f["away_team_id"],
                        f["score"],
                    )
                    for f in new_fixtures
                ],
            )

        return new_fixtures

    async def _save_snapshot(self, fixtures: list[dict]) -> None:
        """Save scraped data to JSON and CSV under reports/courtside/"""
        if not fixtures:
            return

        out_dir = os.path.join("reports", "courtside")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Save fixtures
        fixture_data = [
            {
                "fixture_id": f["fixture_id"],
                "competition_id": f["competition_id"],
                "competition_name": f["competition_name"],
                "home_team_id": f["home_team_id"],
                "home_team_name": f["home_team_name"],
                "away_team_id": f["away_team_id"],
                "away_team_name": f["away_team_name"],
                "score": f["score"],
            }
            for f in fixtures
        ]

        self._save_json_csv(data=fixture_data, out_dir=out_dir, prefix="fixtures", timestamp=ts)

        # Save teams
        team_map = {}
        for f in fixtures:
            if f.get("home_team_id"):
                team_map[f["home_team_id"]] = f.get("home_team_name")
            if f.get("away_team_id"):
                team_map[f["away_team_id"]] = f.get("away_team_name")

        team_data = [
            {"team_id": tid, "team_name": tname} for tid, tname in sorted(team_map.items())
        ]

        self._save_json_csv(data=team_data, out_dir=out_dir, prefix="teams", timestamp=ts)

    def _save_json_csv(self, data: list[dict], out_dir: str, prefix: str, timestamp: str) -> None:
        """Helper to save data as both JSON and CSV"""
        json_path = os.path.join(out_dir, f"{prefix}_{timestamp}.json")
        csv_path = os.path.join(out_dir, f"{prefix}_{timestamp}.csv")

        # Save JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {"generated_at": timestamp, "count": len(data), "items": data},
                f,
                ensure_ascii=False,
                indent=2,
            )

        # Save CSV
        if data:
            fieldnames = list(data[0].keys())
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

    async def _handle_error(self, page: Page, attempt: int) -> None:
        """Save debug info on failure"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.config.screenshot_on_error and page:
            try:
                await page.screenshot(path=f"courtside_error_{timestamp}.png", full_page=True)
                self.logger.info(f"Saved screenshot: courtside_error_{timestamp}.png")
            except Exception as screenshot_error:
                self.logger.error(f"Failed to save screenshot: {screenshot_error}")

    async def _verify_connectivity(self, page: Page) -> bool:
        """Verify we can reach Courtside1891"""
        try:
            response = await page.goto(
                f"{self.config.base_url}/games", timeout=15000, wait_until="domcontentloaded"
            )
            return response.status == 200
        except Exception as e:
            self.logger.error(f"Connectivity check failed: {str(e)}")
            return False

    async def test_scraper(self) -> bool:
        """Test the scraper"""
        try:
            test_results = await self.scrape_data()

            if not test_results:
                self.logger.warning("Test completed but no fixtures found")
                return True

            required_keys = {"fixture_id", "home_team_id", "away_team_id", "competition_id"}
            for result in test_results:
                if not all(key in result for key in required_keys):
                    self.logger.error(f"Test failed - missing keys in result: {result}")
                    return False

            self.logger.info(f"Test passed - found {len(test_results)} fixtures")
            return True

        except Exception as e:
            self.logger.error(f"Test failed with error: {str(e)}")
            return False
