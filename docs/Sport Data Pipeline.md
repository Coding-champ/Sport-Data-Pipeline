## Datenbankschema

Nachfolgend findest du die Entitäten für mein Datenbankschema. Schau dir diese genau an und schlag mir ggf. weiter sinnvolle Merkmale, Relationen und Entitäten vor. Ich habe Fremdschlüssel in Klammern gesetzt.

**Club**
	• Club_id
	• Club_name
	• Club_name_short
	• Club_name_official
	• Founding_year
	• Club_colors
	• Belong_to_association
	• Sport_art
	• (Country_id)
	• (city_id)
	• Club_member
	• Club_nickname
	• (venue_id)
	• [code] (FCB, BVB)
	• Club_address

**Team**
	• Team_id
	• (Club_id)
	• Is_senior
	• Is_male
	• Marketvalue
	• Social_media

**Squad**
	• Squad_id
	• (team_id)
	• Year/ season
	• Player_ids

**Spieler**
	• player_id
	• First_name
	• Secound_name
	• nickname
	• Nationality
	• citizenship
	• Birthdate
	• Birthplace
	• Height
	• Weight
	• Strong_foot
	• [position]
	• (Berater_id)
	• (Ausrüster_id)
	• Is_active

**Trainer**
	• trainer_id
	• Nationality
	• First_name
	• Secound_name
	• Birthdate
	• Birthplace

**Trainer_Career**
	• Trainer_career_id
	• (trainer_id)
	• (team_id)
	• Start_date
	• End_date
	
**Schiedsrichter**
	• referee_id
	• Nationality
	• First_name
	• Secound_name
	• Birthdate
	• birthplace

**Schiedsrichter_erweitert**
	• Type (AR1, AR2, 4th official, VAR)

**Stadion/Halle**
	• venue_id int NOT NULL
	• club_id int NOT NULL (bspw. beim San Siro oder dem SoFi Stadium nicht möglich)
	• venue_name char(100) NOT NULL [update]
	• construction_date date 
	• opening_date date NOT NULL
	• first_game char(200) 
	• capacity_national int NOT NULL [update]
	• capacity_international int [update]
	• building_costs int
	• stands int [update]
	• surface char(50) NOT NULL
	• field_size NUMERIC
	• multi_sports int
	• operator char(100) NOT NULL [update]
	• owner char(100) [update]
	• main_tenant char(100)
	• last_renovation date
	• city char(100) NOT NULL
	• adress char(100) NOT NULL
	• coordinates char(50) NOT NULL
	• official_website char(100)
	• Former_names

**Liga**
	• League_id
	• Country_id
	• League_tier
	• Is_youth_league
	• Is_womens_league
	• (Association_id)
	
**Verband (Governing_Body)**
	• Association_id
	• Association_name
	• Is_national
	
**Wettbewerb**
	• Competition_id
	• Competition_name
	• (Country_id)
	• (association_id)
	• since_year
	• Is_cup
	• Is_youth_league
	• Is_womens_league
	• Is_national

**Saison**
	• Season_id
	• (Competition_id)
	• Year
	• Start_date
	• End_date
	• Is_active
	• Number_of_teams
	• Number_of_games
	• Champion? (Club_id)
	• Top_scorer?
	• Relegated_teams?

**Runde**
	• Round_id
	• (Competition_id)
	• (Season_id)
	• Round_name (matchday)

**Standings**
	• Standing_id
	• (season_id)
	• Mannschaften, Punkte, SUN, Tore, Gegentore, Tordifferenz, Karten, xG
	• Total, Heim, Auswärts
	• Sieger, Europaplätze, Relegation, Play-off?

**Match_Information**
	• Match_id
	• Match_date
	• Match_place
	• (Venue_id)
	• attendance
	• (Home_team_id)
	• (away_team_id)
	• (Referee_id)
	• (Competition_id)
	• (season_id)
	• (matchday_id)
	• Wether_conditions (Temperatur, Witterung)
	• Country_id?
	• Scores? (Total_home_score, total_away_score, ht_home_score, ht_away_score)

**Match_summary**
	• Match_id
	• (Home_team_id)
	• (away_team_id)
	• (home_yellow_cards, away_yellow_cards, home_corner_kicks, away_corner_kicks, home_free_kicks, away_free_kicks, home_penalties, away_penalties)
	• Short (home_possession, away_possession, home_shots_total, away_shots_total, home_shots_target, away_shots_target)
	• advanced

**Match_lineup**
	• (Match_id)
	• (team_id)
	• Formation
	• Captain (player_id)
	• (Player_id)
	• Player_number
	• Player_position
	• Player_appearances
	• Minutes_played
	• Player_ratings (fotmob, opta, sofascore, ...)
	
**Match_Event**
	• Match_id
	• Event_type
	• Event_sub_type
	• Event_type_timestamp
	• (Player_id)

**Match_Odds**
	• Odd_id
	• (Match_id)
	• Bookmaker
	• Market
	• Quote
	• timestamp
	
**Player_Stats**
	• (Player_id)
	• (Match_id)
	• (season_id)?
	• (team_id)?
	• Stats
	
**Team_stats**
	• (Match_id)
	• (team_id)
	• Possession
	• Corner_kicks
	• Free_kicks
	• Throw_ins
	• Offsides

**Player_Injuries**
	• Injury_id
	• (player_id)
	• Date_of_injury
	• Duration
	• Type
	• Number_missed_games

**Player_transfers**
	• Transfer_id
	• (player_id)
	• (Team_id_out) -> kann auch aus Jugend kommen -> kann somit NULL sein
	• (team_id_in) -> kann Karriere beenden oder Vereinslos sein -> kann somit NULL sein
	• Trannsfer_window
	• Transfer_date
	• Transfer_type
	• Transfer_fee
	• Bonus_fees_sum

**Player_Career**
	• (player_id)

**Trophies**
	• Trophy_id
	• Trophy_name
	• (Competition_id)
	• Weight
	• Height
	• Established_in_year
	• picture_url


## Erläuterungen

Hier eine kurze Erläuterung, wie die Entities zusammenhängen: Zu einem **Verein** können mehrere **Mannschaften** gehören (Jugendteams, Seniorenteams, Frauenteams). Zu einem Team gehört ein **Kader** mit Spielern und ein **Trainer**/ Trainerteam. Ein Team spielt in einer **Spielstätte** (Stadion, Halle). Ein Team nimmt an einem **Wettbewerb** (Liga, Pokal) teil. Ein Wettbewerb gehört zu einem **Verband** (Bundesliga - DFL, DFB-Pokal - DFB, Champions League - UEFA, Weltmeisterschaft - FIFA). Ein Team gehört ebenfalls zu einem Verband. Eine **Trophäe** gehört ebenfalls zu einem Wettbewerb. Ein Wettbewerb hat verschiedene **Saisons** und unterschiedliche **Runden** und eine Tabelle. Ein Match findet in einem Wettbewerb statt, hat **Match_Infos**, **Match_Summary**, **Match_Events**, **Match_Line_up**, **Match_Odds** und wird von einem **Schiedsrichter** geleitet.  Jeder Spieler hat eigene **Match Statistiken** und jedes Team hat **Team Statistiken**. Spieler können für ein Spiel **verletzt oder suspended** sein. Spieler können den Verein wechseln und werden somit **transferiert**.  
Alle Personen haben eine **Karriere** mit Spielen, Teams und Statistiken. 


## Datenquellen

Nachfolgend findest du die Links zu den einzelnen Entitäten bzw. oberen Punkten. Dort kannst du Informationen finden. Ich habe dir zusätzlich einige Stellen in den Links mit {} markiert. Diese musst du jeweils anpassen für die unterschiedlichen Anforderungen. Am Ende findest du noch allgemeine Links, die ebenfalls sehr gut sind. Sollte zu den obigen Punkten kein Link aufgeführt sein, dann kannst du in den anderen Links Informationen finden.

**Club**
https://fbref.com/en/country/clubs/ENG/England-Football-Clubs
https://fbref.com/en/country/clubs/{land}/{land clubs}
https://fbref.com/en/squads/19538871/Manchester-United-Stats
https://fbref.com/en/squads/{club id}/{club}

**Team**
https://fbref.com/en/country/clubs/ENG/England-Football-Clubs
https://fbref.com/en/country/clubs/{land}/{land clubs}
https://fbref.com/en/squads/19538871/Manchester-United-Stats
https://fbref.com/en/squads/{club id}/{club}

**Squad**
https://www.transfermarkt.de/fc-bayern-munchen/kader/verein/27/saison_id/2025/plus/1
https://www.transfermarkt.de/{Verein}/kader/verein/{Verein id}/saison_id/{Jahr}/plus/1
https://fbref.com/en/squads/19538871/Manchester-United-Stats
https://fbref.com/en/squads/{club id}/{club}

**Spieler**
https://www.transfermarkt.de/jonathan-tah/profil/spieler/196357
https://www.transfermarkt.de/{spieler name}/profil/spieler/{spieler id}
https://www.whoscored.com/players/475578/history/mats-rots
https://www.whoscored.com/players/{spieler id}/history/{spieler name}
https://www.fussballtransfers.com/spieler/jamal-musiala/
https://www.fussballtransfers.com/spieler/{spieler name}
https://www.fussballzz.de/spieler/ramon-abila/150325
https://www.fussballzz.de/spieler/{spieler name}/{spieler id}
https://www.sofascore.com/de/football/player/telasco-segovia/1106549#tab:details
https://www.sofascore.com/de/football/player/{spieler name}/{spieler id}
https://fbref.com/en/players/45af8a54/Marco-Asensio
https://fbref.com/en/players/{spieler id}/spieler name}
https://www.premierleague.com/en/players/427637/brenden-aaronson/overview
https://www.premierleague.com/en/players/{spieler id}/spieler name}/overview

**Trainer**
https://www.transfermarkt.de/vincent-kompany/profil/trainer/69681
https://www.transfermarkt.de/{trainer name}/profil/trainer/{trainer id}
https://www.fussballtransfers.com/trainer/vincent-kompany
https://www.fussballtransfers.com/trainer/{trainer name}
https://www.fussballzz.de/trainer/greg-vanney/3938
https://www.fussballzz.de/trainer/{trainer name}/{trainer id}
https://www.sofascore.com/de/manager/oscar-pareja/314178
https://www.sofascore.com/de/manager/{trainer name}/{trainer id}

**Schiedsrichter**
https://www.transfermarkt.de/daniel-siebert/profil/schiedsrichter/732
https://www.transfermarkt.de/{schiedsrichter name}/profil/schiedsrichter/{schiedsrichter id}
https://www.whoscored.com/referees/735/show/dennis-higler
https://www.whoscored.com/referees/{schiedsrichter id}/show/{schiedsrichter name}
https://www.fussballzz.de/schiedsrichter/daniel-siebert/4002
https://www.fussballzz.de/schiedsrichter/{schiedsrichter name}/{schiedsrichter id}
https://www.sofascore.com/de/referee/walter-lopez/156189
https://www.sofascore.com/de/referee/{schiedsrichter name}/{schiedsrichter id}

**Stadion/Halle**
https://www.transfermarkt.de/fc-bayern-munchen/stadion/verein/27
https://www.transfermarkt.de/{Verein}/stadion/verein/{Verein id}
https://www.fussballzz.de/estadio.php?id=1741
https://www.fussballzz.de/estadio.php?id={stadion id}
https://www.sofascore.com/de/venue/usa/chase-stadium/28901
https://www.sofascore.com/de/venue/{land}/stadion name}/stadion id}

**Wettbewerb**
https://fbref.com/en/comps/
https://fbref.com/en/comps/9/history/Premier-League-Seasons
https://fbref.com/en/comps/{competition id}/history/{competitions seaseons}
https://fbref.com/en/comps/9/Premier-League-Stats
https://fbref.com/en/comps/9/2024-2025/2024-2025-Premier-League-Stats
https://fbref.com/en/comps/{competition id}/{season}/{competitions seaseons}

**Match_Information**
https://www.transfermarkt.de/spielbericht/index/spielbericht/4623575
https://www.transfermarkt.de/spielbericht/index/spielbericht/{spielbericht id}
https://www.fussballzz.de/spiel/2025-08-22-bayern-munchen-rb-leipzig/11057854
https://www.fussballzz.de/spiel/{game}/{match_id}
https://www.fussballtransfers.com/spiel/5721958797392835299-sv-wehen-wiesbaden-vs-fc-bayern-muenchen
https://www.fussballtransfers.com/spiel/{match_id}
https://fbref.com/en/matches/01590141/Eintracht-Braunschweig-Stuttgart-August-26-2025-DFB-Pokal
https://fbref.com/en/matches/{match id}/{match name}

**Match_summary**
https://www.transfermarkt.de/spielbericht/index/spielbericht/4623575
https://www.transfermarkt.de/spielbericht/index/spielbericht/{spielbericht id}
https://www.fussballzz.de/spiel/2025-08-22-bayern-munchen-rb-leipzig/11057854
https://www.fussballzz.de/spiel/{game}/{match_id}
https://www.fussballtransfers.com/spiel/{match_id}
https://fbref.com/en/matches/01590141/Eintracht-Braunschweig-Stuttgart-August-26-2025-DFB-Pokal
https://fbref.com/en/matches/{match id}/{match name}

**Match_lineup**
https://www.transfermarkt.de/spielbericht/index/spielbericht/4623575
https://www.transfermarkt.de/spielbericht/index/spielbericht/{spielbericht id}
https://www.fussballzz.de/spiel/2025-08-22-bayern-munchen-rb-leipzig/11057854
https://www.fussballzz.de/spiel/{game}/{match_id}
https://www.fussballtransfers.com/spiel/{match_id}
https://fbref.com/en/matches/01590141/Eintracht-Braunschweig-Stuttgart-August-26-2025-DFB-Pokal
https://fbref.com/en/matches/{match id}/{match name}

**Match_Event**
https://www.transfermarkt.de/spielbericht/index/spielbericht/4623575
https://www.transfermarkt.de/spielbericht/index/spielbericht/{spielbericht id}
https://www.fussballzz.de/spiel/2025-08-22-bayern-munchen-rb-leipzig/11057854
https://www.fussballzz.de/spiel/{game}/{match_id}
https://www.fussballtransfers.com/spiel/{match_id}
https://fbref.com/en/matches/01590141/Eintracht-Braunschweig-Stuttgart-August-26-2025-DFB-Pokal
https://fbref.com/en/matches/{match id}/{match name}

**Match_Odds**
https://www.oddsportal.com
https://www.kickform.de
https://www.windrawwin.com
http://www.betexplorer.com

**Player_Stats**
https://www.transfermarkt.de/2-bundesliga/transfers/wettbewerb/L2
https://www.transfermarkt.de/{Liga}/transfers/wettbewerb/{Liga short}

**Player_Injuries**
https://www.transfermarkt.de/borussia-dortmund/sperrenundverletzungen/verein/16/plus/1
https://www.transfermarkt.de/{club name}/sperrenundverletzungen/verein/{club id}/plus/1

**Player_transfers**
https://www.transfermarkt.de/borussia-dortmund/transfers/verein/16/saison_id/2025/pos//detailpos/0/w_s//plus/1
https://www.transfermarkt.de/{club name}/transfers/verein/{club id}/saison_id/{Jahr}/pos//detailpos/0/w_s//plus/1


**Allgemein**
https://www.bundesliga.com/de/bundesliga
https://www.premierleague.com/en
https://www.laliga.com/en-GB/laliga-easports
https://www.legaseriea.it/en
https://ligue1.com/en
