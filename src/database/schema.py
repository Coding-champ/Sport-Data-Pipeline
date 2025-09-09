"""
Database Schema
SQLAlchemy Models für die Sportdatenbank
"""

from sqlalchemy import (
    DECIMAL,
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Sport(Base):
    __tablename__ = "sports"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    code = Column(String(10), nullable=False, unique=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    leagues = relationship("League", back_populates="sport")
    teams = relationship("Team", back_populates="sport")
    players = relationship("Player", back_populates="sport")


class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    code = Column(String(3), nullable=False, unique=True)
    flag_url = Column(Text)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    leagues = relationship("League", back_populates="country")
    teams = relationship("Team", back_populates="country")
    venues = relationship("Venue", back_populates="country")


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True)
    sport_id = Column(Integer, ForeignKey("sports.id"))
    country_id = Column(Integer, ForeignKey("countries.id"))
    name = Column(String(200), nullable=False)
    short_name = Column(String(50))
    logo_url = Column(Text)
    tier = Column(Integer, default=1)
    season_format = Column(String(50))
    is_active = Column(Boolean, default=True)
    external_ids = Column(JSON)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    sport = relationship("Sport", back_populates="leagues")
    country = relationship("Country", back_populates="leagues")
    seasons = relationship("Season", back_populates="league")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    sport_id = Column(Integer, ForeignKey("sports.id"))
    name = Column(String(200), nullable=False)
    short_name = Column(String(50))
    city = Column(String(100))
    country_id = Column(Integer, ForeignKey("countries.id"))
    founded_year = Column(Integer)
    logo_url = Column(Text)
    colors = Column(JSON)
    website = Column(Text)
    is_active = Column(Boolean, default=True)
    external_ids = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    sport = relationship("Sport", back_populates="teams")
    country = relationship("Country", back_populates="teams")
    home_matches = relationship(
        "Match", foreign_keys="Match.home_team_id", back_populates="home_team"
    )
    away_matches = relationship(
        "Match", foreign_keys="Match.away_team_id", back_populates="away_team"
    )


class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    city = Column(String(100))
    country_id = Column(Integer, ForeignKey("countries.id"))
    capacity = Column(Integer)
    surface = Column(String(50))
    indoor = Column(Boolean, default=False)
    latitude = Column(DECIMAL(10, 8))
    longitude = Column(DECIMAL(11, 8))
    image_url = Column(Text)
    external_ids = Column(JSON)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    country = relationship("Country", back_populates="venues")
    matches = relationship("Match", back_populates="venue")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    sport_id = Column(Integer, ForeignKey("sports.id"))
    first_name = Column(String(100))
    last_name = Column(String(100))
    birth_date = Column(Date)
    birth_place = Column(String(100))
    nationality = Column(String(3))
    height_cm = Column(Integer)
    weight_kg = Column(Integer)
    preferred_foot = Column(String(10))
    photo_url = Column(Text)
    is_active = Column(Boolean, default=True)
    external_ids = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    sport = relationship("Sport", back_populates="players")
    season_stats = relationship("SeasonPlayerStats", back_populates="player")


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    sport_id = Column(Integer, ForeignKey("sports.id"))
    name = Column(String(50), nullable=False)
    short_name = Column(String(10))
    category = Column(String(50))
    created_at = Column(DateTime, default=func.now())


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    name = Column(String(50), nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    is_current = Column(Boolean, default=False)
    external_ids = Column(JSON)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    league = relationship("League", back_populates="seasons")
    matches = relationship("Match", back_populates="season")


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey("seasons.id"))
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    venue_id = Column(Integer, ForeignKey("venues.id"))
    match_date = Column(DateTime, nullable=False)
    status = Column(String(20))
    home_score = Column(Integer)
    away_score = Column(Integer)
    attendance = Column(Integer)
    referee = Column(String(100))
    weather_conditions = Column(JSON)
    match_stats = Column(JSON)
    external_ids = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    season = relationship("Season", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    venue = relationship("Venue", back_populates="matches")


class SeasonPlayerStats(Base):
    __tablename__ = "season_player_stats"

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    season_id = Column(Integer, ForeignKey("seasons.id"))
    position_id = Column(Integer, ForeignKey("positions.id"))
    matches_played = Column(Integer, default=0)
    minutes_played = Column(Integer, default=0)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    stats_data = Column(JSON)
    market_value = Column(DECIMAL(12, 2))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    player = relationship("Player", back_populates="season_stats")


class BettingOdds(Base):
    __tablename__ = "betting_odds"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    bookmaker = Column(String(100))
    market_type = Column(String(50))
    odds_data = Column(JSON)
    timestamp = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
