import requests
from bs4 import BeautifulSoup, Comment
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import os

LOAD_AND_SAVE_SNAPSHOT = False #change this later

if LOAD_AND_SAVE_SNAPSHOT:
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    url = "https://fbref.com/en/comps/9/Premier-League-Stats"
    driver.get(url)
    #allow page and js to load
    time.sleep(5)

    with open("fbref_snapshot.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

    driver.quit()
    print("Page saved to fbref_snapshot.html")

#parsing of locally saved html
with open("fbref_snapshot.html", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

#find all tables with stats_table class
tables = soup.select("table.stats_table")
print(f"Found {len(tables)} tables")

# Debug: print table captions to see what's available
for i, table in enumerate(tables):
    caption = table.caption.text if table.caption else "No caption"
    print(f"Table {i}: {caption}")

target_table = None
for table in tables:
    if table.caption and "Squad Standard Stats" in table.caption.text:
        target_table = table
        break

if not target_table:
    # Try to find any table with team links as fallback
    for table in tables:
        links = table.find_all("a")
        team_links = [l.get("href") for l in links if '/squads/' in l.get("href", "")]
        if team_links:
            target_table = table
            print(f"Found table with {len(team_links)} team links")
            break
    
    if not target_table:
        raise Exception("Could not find team table")

# Debug: print all hrefs in the target table
for a in target_table.find_all("a"):
    print(a.get("href"))

#extract team URLs
links = target_table.find_all("a")
season = "2024-2025"
team_links = [
    l.get("href") for l in links
    if l.get("href") and l.get("href").startswith("/en/squads/") and f"/{season}/" in l.get("href")
]
team_urls = [f"https://fbref.com{l}" for l in team_links]
print(f"Found {len(team_urls)} team URLs")
print(team_urls)

#extract data for all teams
all_matches = []

# use selenium for team pages to avoid being rate limited
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

for team_url in team_urls:
    team_name = team_url.split("/")[-1].replace("-Stats", "").replace("-", " ")
    print(f"Scraping: {team_name}")

    try:
        driver.get(team_url)
        time.sleep(3)  # Let page load
        
        data = driver.page_source
        soup = BeautifulSoup(data, "lxml")

        # Debug: Check what tables are available on the team page
        print(f"\nChecking {team_name} page...")
        all_tables = soup.find_all("table")
        print(f"Found {len(all_tables)} tables on {team_name} page")
        
        # Print table captions to see what's available
        for i, table in enumerate(all_tables[:5]):  # Check first 5 tables
            caption = table.find("caption")
            if caption:
                print(f"  Table {i}: {caption.text.strip()}")
            else:
                print(f"  Table {i}: No caption")
        
        #matches table
        try:
            matches = pd.read_html(data, match="Scores & Fixtures")[0]
        except Exception as e:
            print(f"Could not find match data for {team_name}: {e}")
            continue

        shooting_link = soup.find("a", href=True, string="Shooting")
        if not shooting_link:
            print(f"No shooting stats found for {team_name}")
            continue
        
        shooting_url = f"https://fbref.com{shooting_link['href']}"
        driver.get(shooting_url)
        time.sleep(2)
        shooting_data = driver.page_source
        shooting = pd.read_html(shooting_data, match="Shooting")[0]
        shooting.columns = shooting.columns.droplevel()

        try:
            team_data = matches.merge(
                shooting[["Date", "Sh", "SoT", "Dist", "FK", "PK", "PKatt"]],
                on="Date"
            )
            team_data["Team"] = team_name
            all_matches.append(team_data)
            print(f"Successfully processed {team_name}")
        except Exception as e:
            print(f"Merge error for {team_name}: {e}")
            continue

        time.sleep(2)  #small delay between teams
        
    except Exception as e:
        print(f"Error processing {team_name}: {e}")
        continue

driver.quit()

#final merge
if all_matches:
    df = pd.concat(all_matches)
    df.columns = [c.lower() for c in df.columns]
    print(df.head())
    df.to_csv("matches.csv", index=False)
    print("Data saved to matches.csv")
else:
    print("No match data collected")
