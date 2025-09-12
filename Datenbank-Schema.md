# Datenbank-Schema für Sport-Data-Pipeline

## Übersicht

Dieses Dokument beschreibt das Datenmodell der Sport-Data-Pipeline, die für die Verwaltung von Sportdaten für Fußball, Basketball und American Football entwickelt wurde. Das Schema nutzt PostgreSQL als Datenbank und macht extensiven Gebrauch von JSONB für flexible Datenstrukturen.

## Unterstützte Sportarten

Das Schema unterstützt drei Hauptsportarten:
- **Football** (Fußball/Soccer)
- **Basketball** 
- **American Football**

## Schema-Architektur

### Grundprinzipien

1. **Multi-Sport-Unterstützung**: Jede Hauptentität ist mit einer Sportart verknüpft
2. **Flexible Datenstruktung**: JSONB wird für sportspezifische Statistiken verwendet
3. **Historisierung**: SCD2-Ansatz für sich ändernde Daten (Vereinsnamen, Stadionnamen)
4. **Audit-Felder**: Jede Tabelle enthält Herkunft und Zeitstempel
5. **Normalisierung**: Lookup-Tabellen für wiederkehrende Werte
6. **Technologie-Integration**: Unterstützung für VAR, GPS-Tracking, etc.

## ENUM-Typen

### Kernsystem
```sql
sport_enum: 'football', 'basketball', 'american_football'
team_type: 'club', 'national', 'youth', 'women', 'academy'
strong_foot: 'left', 'right', 'both'
surface_type: 'grass', 'hybrid', 'artificial', 'indoor', 'hardwood', 'turf'
```

### Personal und Funktionen
```sql
official_role: 'referee', 'ar1', 'ar2', 'fourth', 'var', 'avar', 'umpire', 'line_judge', 'field_judge'
staff_role: 'head_coach', 'assistant_coach', 'gk_coach', 'fitness_coach', 'analyst', 'physio', 'medical', 'team_manager', 'nutritionist', 'psychologist', 'equipment_manager', 'video_analyst', 'scout'
```

### Medizin und Verletzungen
```sql
injury_type: 'muscle', 'bone', 'joint', 'ligament', 'concussion', 'illness', 'other'
absence_reason: 'injury', 'suspension', 'illness', 'national_duty', 'personal', 'coach_decision'
```

### Technologie
```sql
technology_type: 'var', 'goal_line', 'offside', 'gps', 'heart_rate', 'player_tracking'
```

### Wettsystem
```sql
price_type: 'open', 'close', 'live'
season_type: 'cross_year', 'calendar_year'
```

## Hauptentitäten

### 1. Kern-Lookup-Tabellen

#### `sport`
Definiert die unterstützten Sportarten mit ihren Grundeigenschaften.
- `sport_id`: Primärschlüssel
- `sport_type`: ENUM-Wert
- `name`: Anzeigename
- `governing_body`: Dachverband (FIFA, FIBA, NFL)

#### `country` & `city`
Geografische Referenzdaten für Vereine, Spieler und Veranstaltungsorte.

#### `association`
Sportverbände (FIFA, UEFA, DFB, etc.) mit hierarchischer Struktur über `parent_association_id`.

### 2. Organisationen

#### `club`
Sportvereine mit Multi-Sport-Unterstützung:
- Verknüpfung zur `sport` Tabelle
- Kommerzielle Informationen (Hauptsponsor, Ausrüster)
- Social Media Präsenz (JSONB)
- Unterstützung für Multi-Sport-Vereine über `parent_club_id`

#### `venue`
Spielstätten mit erweiterten Funktionen:
- Multi-Sport-Unterstützung (`supported_sports` JSONB)
- Sportspezifische Abmessungen (`field_dimensions` JSONB)
- Technologie-Ausstattung (VAR, Torlinientechnik)
- Kapazitätsdetails (`capacity_details` JSONB)

### 3. Teams und Personen

#### `team`
Teams mit sportspezifischen Eigenschaften:
- Verknüpfung zu `sport` und optional zu `club`
- Nachwuchsförderung über `academy_level` und `parent_team_id`
- Leistungsverfolgung (`current_form`, `season_objectives` JSONB)

#### `player`
Spieler mit umfassenden Profilen:
- Sportspezifische Attribute (`sport_attributes` JSONB)
- Nachwuchslaufbahn (`youth_career` JSONB)
- Medizinische und Fitness-Daten
- Karrierestatistiken (`career_stats` JSONB)
- Social Media Präsenz

#### `staff_member` & `medical_staff`
Erweiterte Personalverwaltung:
- Qualifikationen und Zertifizierungen (JSONB)
- Spezialisierungen und Sprachen
- Medizinisches Personal mit Lizenzen

### 4. Wettbewerbe und Saisons

#### `competition`
Sportspezifische Wettbewerbe:
- Wettbewerbsformat (`competition_format` JSONB)
- Preisgelder (`prize_money` JSONB)

#### `season`
Saisons mit flexiblen Regeln:
- Saisonspezifische Regeln (`rules` JSONB)
- Unterstützung für verschiedene Saisontypen

### 5. Spiele und Ergebnisse

#### `match`
Erweiterte Spieldaten:
- Sportartspezifische Daten (`sport_specific_data` JSONB)
- Technologie-Nutzung (`technology_used` JSONB)
- Übertragungsinformationen (`broadcast_info` JSONB)
- Wetterbedingungen mit mehr Details

#### `match_result`
Flexible Ergebniserfassung:
- Sportspezifische Punkteverteilung (`score_breakdown` JSONB)
- Verschiedene Siegarten (`win_type`)

### 6. Medizin und Gesundheit

#### `player_injury`
Umfassende Verletzungsdokumentation:
- Behandlungsplan (`treatment_plan` JSONB)
- Medizinische Berichte (`medical_reports` JSONB)
- Verknüpfung zu medizinischem Personal

#### `player_fitness_record`
Fitness-Monitoring:
- Fitnessdaten (`fitness_data` JSONB)
- Regelmäßige Gesundheitschecks

### 7. Technologie-Integration

#### `match_technology_data`
VAR, Torlinientechnik und andere Technologien:
- Entscheidungsergebnisse (`decision_result` JSONB)
- Vertrauenslevel der Technologie

#### `player_tracking_data`
GPS und Leistungsdaten:
- Physische Metriken (Laufstrecke, Geschwindigkeit)
- Positionsdaten
- Leistungsmetriken (`performance_metrics` JSONB)

### 8. Statistiken

#### `team_match_stats`
Teamstatistiken mit sportspezifischen Daten:
- Gemeinsame Statistiken (Ballbesitz)
- Sportspezifische Metriken:
  - `football_stats` JSONB
  - `basketball_stats` JSONB
  - `american_football_stats` JSONB
- Taktische Analysen (`tactical_analysis` JSONB)

#### `player_match_stats`
Umfassende Spielerstatistiken:
- Grundlegende Fußballstatistiken (Tore, Assists, Pässe)
- Basketball-Statistiken (JSONB)
- American Football-Statistiken (JSONB)
- Physische Leistungsdaten
- Positionsdaten (`heat_map_data` JSONB)

### 9. Wettsystem

#### `betting_market` & `betting_outcome`
Sportspezifische Wettmärkte:
- Fußball: 1X2, Über/Unter Tore, Asiatisches Handicap
- Basketball/American Football: Moneyline, Point Spread, Total Points

#### `match_odd`
Erweiterte Quotenverfolgung:
- Live-Wetten Unterstützung
- Zeitstempel für Quotenentwicklung
- Aktueller Spielstand bei Live-Quoten

## JSONB-Nutzung

Das Schema macht extensiven Gebrauch von JSONB für flexible Datenstrukturen:

### Beispiele für JSONB-Felder:

**Social Media (`social_media`)**:
```json
{
  "twitter": "@player_handle",
  "instagram": "@player_insta",
  "tiktok": "@player_tiktok",
  "youtube": "channel_url"
}
```

**Basketball-Statistiken (`basketball_stats`)**:
```json
{
  "points": 24,
  "rebounds": 8,
  "assists": 6,
  "steals": 2,
  "blocks": 1,
  "turnovers": 3,
  "field_goals_made": 9,
  "field_goals_attempted": 15,
  "three_pointers_made": 3,
  "three_pointers_attempted": 7
}
```

**Spielstätten-Abmessungen (`field_dimensions`)**:
```json
{
  "football": {"length": 105, "width": 68},
  "basketball": {"length": 28, "width": 15},
  "american_football": {"length": 109.7, "width": 48.8}
}
```

**Technologie-Entscheidungen (`decision_result`)**:
```json
{
  "var_decision": "goal_confirmed",
  "original_call": "goal",
  "review_duration_seconds": 45,
  "certainty": "clear_and_obvious"
}
```

## Beziehungsdiagramm

### Hauptbeziehungen:

1. **Sport → Alle Hauptentitäten**: Jede Entität ist sportspezifisch
2. **Club → Team → Player**: Hierarchische Vereinsstruktur
3. **Competition → Season → Match**: Wettbewerbshierarchie
4. **Match → Stats/Events**: Ein-zu-Viele Beziehungen für Spieldaten
5. **Player → Injuries/Fitness**: Gesundheitsdaten-Tracking
6. **Staff → Medical Staff**: Spezialisierung des Personals

### Referentielle Integrität:

- **ON DELETE RESTRICT**: Bei kritischen Beziehungen (Sport, Land)
- **ON DELETE CASCADE**: Bei abhängigen Daten (Statistiken, Events)
- **ON DELETE SET NULL**: Bei optionalen Referenzen

## Indizierung

Das Schema implementiert eine umfassende Indizierungsstrategie:

- **Primär-/Fremdschlüssel**: Automatische Indizierung
- **Häufige Filter**: Sport-ID, Datum, Status
- **Zusammengesetzte Indizes**: Match-Team, Spieler-Match Kombinationen
- **JSONB-Indizes**: Für häufig abgefragte JSON-Felder

## Audit und Datenherkunft

Alle Haupttabellen enthalten:
- `source_url`: Herkunfts-URL der Daten
- `scraped_at`: Zeitpunkt der Datenerfassung
- `created_at`: Erstellungszeitpunkt
- `updated_at`: Letzte Aktualisierung (automatische Trigger)

## Erweiterbarkeit

Das Schema ist für zukünftige Erweiterungen konzipiert:

1. **Neue Sportarten**: Einfache Erweiterung über `sport` Tabelle
2. **Neue Statistiken**: JSONB-Felder für flexible Datenstrukturen
3. **Neue Technologien**: Erweiterbares `technology_type` ENUM
4. **Neue Märkte**: Sportspezifische Wettmärkte

## Best Practices für die Nutzung

1. **JSONB-Abfragen**: Nutzen Sie GIN-Indizes für komplexe JSON-Abfragen
2. **Datenvalidierung**: Nutzen Sie CHECK Constraints für Geschäftsregeln
3. **Partitionierung**: Erwägen Sie Partitionierung für große Datensätze (Matches, Stats)
4. **Archivierung**: Implementieren Sie Archivierungsstrategien für historische Daten

Dieses Schema bietet eine solide Grundlage für eine umfassende Sportdaten-Pipeline mit Fokus auf Flexibilität, Skalierbarkeit und Multi-Sport-Unterstützung.