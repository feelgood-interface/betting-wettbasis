import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
import re
import datetime
import logging
from prettytable import PrettyTable

logging.basicConfig(level=logging.CRITICAL)


@dataclass
class Fixture:
    date_time: datetime.datetime
    team_a: str
    team_b: str
    tip_text: str
    odds: float
    league: str
    stake: str
    link: str
    comment: str = None


def get_soup(base_url, headers=None, parameters=None):
    try:
        req = requests.get(base_url, headers=headers, params=parameters)
        req.raise_for_status()
        soup = BeautifulSoup(req.text, 'lxml')
        return soup
    except requests.exceptions.HTTPError as e:
        print(e)
        return None


def get_bet_of_the_day():
    logging.debug(f'Getting bet of the day')
    url = 'https://www.wettbasis.com/sportwetten-tipps'
    soup = get_soup(url)

    try:
        tip_element = soup.find('div', attrs={'class': 'row sportwetten-news-up'})
        tip_link = tip_element.find('div', {'class': 'cta-footer'}).find('a', href=True)['href']
        return tip_link
    except AttributeError:
        logging.exception('Could not get bet of the day')
        print('Could not get bet of the day')
        return None


def get_tip_links(url):
    logging.debug(f'Getting tips for URL: {url}')
    # Boolean to keep track if any up-to-date tips were added
    keep_scraping = False
    tip_links = []

    soup = get_soup(url)

    tip_elements = soup.findAll('div', attrs={'class': 'card-body'})
    for tip_element in tip_elements:
        date_label = tip_element.find('span', text=re.compile('Datum'), attrs={'class': 'preview-label'})
        if date_label:
            date_element = date_label.parent.find('span', attrs={'class': 'preview-data'})
            date = datetime.datetime.strptime(date_element.text.strip(), '%d.%m.%Y').date()
            if date < datetime.date.today():
                continue

        tip_link = tip_element.find('h4', {'class': 'card-title'}).find('a', href=True)['href']
        tip_links.append(tip_link)
        keep_scraping = True

    return keep_scraping, tip_links


def visit_link(url):
    soup = get_soup(url)
    title = soup.find('h1', {'class': 'entry-title'}).text
    try:
        team_a = re.search(r'(.*?) (vs.|–)', title).group(1)
        team_b = re.search(r'(?:vs.|–) (.*?) Tipp', title).group(1)
    except AttributeError:
        team_a = title
        team_b = None

    tip_details = soup.find('div', {'class': 'tip-details'})
    if tip_details:
        tip_title = soup.find('div', {'class': 'tip-details__tip fancy-title'}).text.strip().replace('\n', ' ')
        tip_text = re.search(r'(.*) zu Quote', tip_title).group(1)
        odds = float(re.search(r'zu Quote (.*)', tip_title).group(1))

        league = tip_details.find('span', text=re.compile('Wettbewerb'), attrs={'class': 'details-label'})\
            .parent.find('span', attrs={'class': 'details-data'}).text.strip()
        date_element = tip_details.find('span', text=re.compile('Datum'), attrs={'class': 'details-label'})\
            .parent.find('span', attrs={'class': 'details-data'})
        date_time = datetime.datetime.strptime(date_element.text.strip(), '%d.%m.%Y, %H:%M Uhr')
        stake = tip_details.find('span', text=re.compile('Einsatz'), attrs={'class': 'details-label'}) \
            .parent.find('span', attrs={'class': 'details-data'}).text.strip()

        tip = Fixture(date_time, team_a, team_b, tip_text, odds, league, stake, url)
        return tip
    else:
        try:
            # probably e-sports
            value_tip = soup.find('div', {'class': 'valueTip'})
            tip_title = value_tip.find('div', {'class': 'valueTip__tip fancy-title'}).text.strip().replace('\n', ' ')

            # tip_text = re.search(r'(.*) zu', tip_title).group(1)
            # odds = float(re.match(r'zu (.*)', tip_title).group((1)))
            search_str = 'zu '
            i = tip_title.rindex(search_str)
            tip_text = tip_title[:i]
            odds = float(tip_title[i+len(search_str):])

            # date_element = soup.find('h2', text=re.compile(r'beste Quoten'))
            date_element = soup.find(lambda tag: tag.name == 'h2' and 'beste Quoten' in tag.text)
            date = re.search(r'beste Quoten \* (.*)', date_element.text.strip()).group(1)
            time_element = soup.find('table', attrs={'class': 'bonus-table'}).find('td', text=re.compile(' Uhr '))
            time = re.search(r'(.*) Uhr', time_element.text).group(1)
            date_time = datetime.datetime.strptime(date+time, '%d.%m.%Y%H:%M')

            tip = Fixture(date_time, team_a, team_b, tip_text, odds, None, None, url)
            return tip
        except:
            logging.exception(f'Could not scrape {url}')
            print(f'Could not scrape {url}')
            return None


def filter_tips_today(tips):
    # get all tips before tomorrow 10:00
    tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)
    tomorrow_datetime = datetime.datetime(hour=10, minute=00, second=00,
                                          year=tomorrow_date.year, month=tomorrow_date.month, day=tomorrow_date.day)
    tomorrow_datetime.replace()
    tips_today = [x for x in tips
                  if x.date_time <= tomorrow_datetime]
    tips_today.sort(key=lambda x: x.date_time)
    tips_today.sort(key=lambda x: (x.comment if x.comment else ''), reverse=True)

    return tips_today


def get_tips():
    tips = []
    page = 1
    keep_scraping = True

    tip_links = []
    # tip_links.append(
    #     'https://www.wettbasis.com/sportwetten-tipps/team-we-vs-invictus-gaming-tipp-quote-lpl-spring-2021')
    while keep_scraping:
        url = f'https://www.wettbasis.com/sportwetten-tipps/page/{page}'
        keep_scraping, new_links = get_tip_links(url)
        tip_links += new_links
        page += 1

    for link in tip_links:
        tip = visit_link(link)
        if tip:
            tips.append(tip)

    bet_of_the_day_link = get_bet_of_the_day()
    if bet_of_the_day_link:
        try:
            [x for x in tips if x.link == bet_of_the_day_link][0].comment = 'Bet of the Day'
        except IndexError:
            tip = visit_link(bet_of_the_day_link)
            tip.comment = 'Bet of the Day'
            if tip:
                tips.append(tip)

    # tips.sort(key=lambda x: x.date_time)
    todays_tips = filter_tips_today(tips)
    table = PrettyTable(['Date', 'Fixture', 'Tip', 'Odds', 'Stake', 'League', 'Comment', 'Link'])
    for tip in todays_tips:
        table.add_row([tip.date_time,
                       f"{tip.team_a if tip.team_a else ''} vs {tip.team_b if tip.team_b else ''}",
                       tip.tip_text if tip.tip_text else '',
                       tip.odds if tip.odds else '',
                       tip.stake if tip.stake else '',
                       tip.league if tip.league else '',
                       tip.comment if tip.comment else '',
                       tip.link if tip.link else ''])
    print(table)


get_tips()
