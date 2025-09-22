"""Global pytest fixtures for test suite consolidation.

Centralizes:
 - Project root path insertion (so individual tests don't repeat sys.path hacks)
 - Reusable HTML sample snippets for Bundesliga club & player scraping
 - Common mapper fixtures
"""

import sys
from pathlib import Path
import pytest

# Ensure project root (containing src/) is on sys.path once
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.term_mapper import TermMapper  # noqa: E402


# -------------------- Mapper Fixtures -------------------- #

@pytest.fixture(scope="session")
def position_mapper():
    """Session-scoped default position mapper."""
    return TermMapper.default_position_mapper()


# -------------------- HTML Fixtures -------------------- #

@pytest.fixture
def sample_clubs_html():
    return (
        """
        <html>
        <body>
            <div class="clubs-list">
                <a href="/de/bundesliga/clubs/fc-bayern-muenchen">FC Bayern München</a>
                <a href="/de/bundesliga/clubs/borussia-dortmund">Borussia Dortmund</a>
                <a href="/de/bundesliga/clubs/rb-leipzig">RB Leipzig</a>
            </div>
        </body>
        </html>
        """
    )


@pytest.fixture
def sample_club_html():
    return (
        """
        <html>
        <head>
            <title>FC Bayern München - Bundesliga</title>
            <meta property="og:title" content="FC Bayern München" />
        </head>
        <body>
            <h1 class="club-name">FC Bayern München</h1>
            <div class="club-info">
                <dt>Stadium</dt><dd>Allianz Arena</dd>
                <dt>Founded</dt><dd>1900</dd>
                <dt>Coach</dt><dd>Thomas Tuchel</dd>
                <dt>City</dt><dd>München</dd>
            </div>
            <a href="/de/bundesliga/clubs/fc-bayern-muenchen/squad">Squad</a>
        </body>
        </html>
        """
    )


@pytest.fixture
def sample_squad_html():
    return (
        """
        <html>
        <body>
            <h1>Team Squad</h1>
            <table>
                <tr>
                    <td><a href="/de/bundesliga/spieler/manuel-neuer">Manuel Neuer</a></td>
                    <td>GK, #1</td>
                </tr>
                <tr>
                    <td><a href="/de/bundesliga/spieler/thomas-mueller">Thomas Müller</a></td>
                    <td>FW, #25</td>
                </tr>
                <tr>
                    <td><a href="/de/bundesliga/spieler/joshua-kimmich">Joshua Kimmich</a></td>
                    <td>MF, #6</td>
                </tr>
            </table>
        </body>
        </html>
        """
    )


@pytest.fixture
def sample_squad_html_with_noise():
    return (
        """
        <html>
        <body>
            <h1>Club Squad</h1>
            <nav class="main-nav">
                <a href="/de/bundesliga/spieler/random-player-1">Random Player 1</a>
                <a href="/de/bundesliga/spieler/random-player-2">Random Player 2</a>
            </nav>
            <table class="squad-table">
                <tr>
                    <td><a href="/de/bundesliga/spieler/manuel-neuer">Manuel Neuer</a></td>
                    <td>GK, #1, Age: 37</td>
                </tr>
                <tr>
                    <td><a href="/de/bundesliga/spieler/thomas-mueller">Thomas Müller</a></td>
                    <td>FW, #25, Age: 34</td>
                </tr>
                <tr>
                    <td><a href="/de/bundesliga/spieler/joshua-kimmich">Joshua Kimmich</a></td>
                    <td>MF, #6, Age: 28</td>
                </tr>
            </table>
            <footer>
                <a href="/de/bundesliga/spieler/another-random">Another Random</a>
            </footer>
        </body>
        </html>
        """
    )


@pytest.fixture
def sample_player_html():
    return (
        """
        <html>
        <head>
            <title>Manuel Neuer - Bundesliga</title>
        </head>
        <body>
            <h1 class="player-name">Manuel Neuer</h1>
            <div class="player-info">
                <dt>Position</dt><dd>Goalkeeper</dd>
                <dt>Number</dt><dd>1</dd>
                <dt>Born</dt><dd>27.03.1986</dd>
                <dt>Nationality</dt><dd>Germany</dd>
                <dt>Height</dt><dd>193 cm</dd>
                <dt>Weight</dt><dd>92 kg</dd>
            </div>
            <section class="season-stats">
                <dt>Appearances</dt><dd>25</dd>
                <dt>Goals</dt><dd>0</dd>
                <dt>Assists</dt><dd>1</dd>
            </section>
        </body>
        </html>
        """
    )

