from typing import Optional, Tuple
import argparse
import os
import re
import sys
from datetime import datetime

import psycopg2
import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def get_db_conn():
    host = os.getenv("PGHOST", os.getenv("POSTGRES_HOST", "localhost"))
    port = int(os.getenv("PGPORT", os.getenv("POSTGRES_PORT", "6543")))
    user = os.getenv("PGUSER", os.getenv("POSTGRES_USER", "sports_user"))
    password = os.getenv("PGPASSWORD", os.getenv("POSTGRES_PASSWORD", "sports_password"))
    dbname = os.getenv("PGDATABASE", os.getenv("POSTGRES_DB", "sports_data"))
    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_agent_and_market_value(
    html: str,
) -> Tuple[Optional[str], Optional[Tuple[datetime, Optional[float], Optional[str]]]]:
    """
    Returns:
      agent_name or None,
      (valuation_date, value_eur, currency) or None
    """
    soup = BeautifulSoup(html, "html.parser")

    # Agent name: often linked near 'Berater' or agency link
    agent_name = None
    for a in soup.select("a[href*='/beraterfirma/']"):
        name = a.get_text(strip=True)
        if name:
            agent_name = name
            break

    # Market value current: e.g. "30,00 Mio. €  Letzte Änderung: 05.06.2025"
    mv_text = None
    for el in soup.find_all(text=re.compile(r"Letzte Änderung:")):
        full = el.strip()
        if "Letzte Änderung:" in full:
            # try to get sibling text for the value
            parent_text = el.parent.get_text(" ", strip=True)
            mv_text = parent_text
            break
    valuation_date = None
    value_eur = None
    currency = None
    if mv_text:
        # Extract date
        m_date = re.search(r"Letzte Änderung:\s*(\d{2}\.\d{2}\.\d{4})", mv_text)
        if m_date:
            valuation_date = datetime.strptime(m_date.group(1), "%d.%m.%Y").date()
        # Extract value & currency (rough heuristic)
        # Examples: "30,00 Mio. €", "8,5 Mio. €"
        m_val = re.search(r"([0-9.,]+)\s*(Mio\.|Tsd\.)?\s*€", mv_text)
        if m_val:
            raw = m_val.group(1).replace(".", "").replace(",", ".")
            scale = m_val.group(2)
            try:
                v = float(raw)
                if scale == "Mio.":
                    v *= 1_000_000
                elif scale == "Tsd.":
                    v *= 1_000
                value_eur = v
                currency = "EUR"
            except ValueError:
                pass

    mv_tuple = None
    if valuation_date or value_eur:
        mv_tuple = (valuation_date or datetime.utcnow().date(), value_eur, currency)

    return agent_name, mv_tuple


def upsert_agent(cur, name: str) -> int:
    cur.execute(
        """
        INSERT INTO agent(name)
        VALUES (%s)
        ON CONFLICT DO NOTHING
        RETURNING agent_id
        """,
        (name,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    # fetch existing id
    cur.execute("SELECT agent_id FROM agent WHERE name=%s", (name,))
    return cur.fetchone()[0]


def upsert_player_agent_assignment(cur, player_id: int, agent_id: int, source_url: str):
    # allow multiple assignments over time; we insert an open-ended record if not exists
    cur.execute(
        """
        INSERT INTO player_agent_assignment(player_id, agent_id, from_date, source_url, scraped_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT DO NOTHING
        """,
        (player_id, agent_id, None, source_url),
    )


def upsert_player_market_value(
    cur,
    player_id: int,
    valuation_date: datetime.date,
    value_eur: Optional[float],
    currency: Optional[str],
    source_url: str,
):
    cur.execute(
        """
        INSERT INTO player_market_value(player_id, valuation_date, value_eur, currency, source_url, scraped_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (player_id, valuation_date)
        DO UPDATE SET value_eur = EXCLUDED.value_eur, currency = EXCLUDED.currency, source_url = EXCLUDED.source_url, updated_at = NOW()
        """,
        (player_id, valuation_date, value_eur, currency, source_url),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Ingest agent & market value from a Transfermarkt player profile page"
    )
    parser.add_argument("--player-id", type=int, required=True, help="Internal player_id in DB")
    parser.add_argument("--url", type=str, required=True, help="Transfermarkt player profile URL")
    parser.add_argument("--no-agent", action="store_true", help="Skip agent ingestion")
    parser.add_argument("--no-market", action="store_true", help="Skip market value ingestion")
    args = parser.parse_args()

    html = fetch_html(args.url)
    agent_name, mv_tuple = parse_agent_and_market_value(html)

    conn = get_db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                if not args.no_agent and agent_name:
                    agent_id = upsert_agent(cur, agent_name)
                    upsert_player_agent_assignment(cur, args.player_id, agent_id, args.url)
                    print(f"Agent upserted: {agent_name} (agent_id={agent_id})")
                elif not args.no_agent:
                    print("Agent not found on page")

                if not args.no_market and mv_tuple:
                    valuation_date, value_eur, currency = mv_tuple
                    upsert_player_market_value(
                        cur, args.player_id, valuation_date, value_eur, currency, args.url
                    )
                    print(
                        f"Market value upserted: player_id={args.player_id} date={valuation_date} value_eur={value_eur}"
                    )
                elif not args.no_market:
                    print("Market value not found on page")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
