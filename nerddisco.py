from __future__ import print_function
from difflib import SequenceMatcher
import sys
import discogs_client
import csv
import re
import os

csv_path = sys.argv[1]
token = sys.argv[2]
username = sys.argv[3]

alphanumeric = re.compile('^[\w\d\s]+$')

# The Python 2.7 CSV module does not support non-ASCII characters
reload(sys)
sys.setdefaultencoding('utf8')

discogs = discogs_client.Client('Nerdisco/0.1', user_token=token)


def error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def parse_records(csv_path):
    # with io.open(csv_path, mode="r", encoding="utf-8") as csv_file:
    with open(csv_path, 'r') as csv_file:
        return [r for r in csv.DictReader(csv_file)]


def search(artist, title, label, format):
    if not alphanumeric.match(artist):
        # The API can't match non alphanumeric artists :(
        error("Uh oh! Non-alphanumeric artist!")
        results = discogs.search(
            release_title=title,
            label=label,
            format=format,
            type='release')
        filtered = [r for r in results if artist.strip() in [a.name.strip() for a in r.artists]]
        if len(filtered) > 0:
            return filtered

        results = discogs.search(
            release_title=title,
            format='Vinyl',
            type='release')
        filtered = [r for r in results if artist.strip() in [a.name.strip() for a in r.artists]]
        if len(filtered) > 0:
            return filtered

    results = discogs.search(
        artist=artist,  # remove non-alphanumeric, the API can't handle them
        release_title=title,
        label=label,
        format=format,
        type='release')

    if results.count > 0:
        return results

    if '&' in artist:
        print("No records found, possible multiple artists...")
        for a in artist.split('&'):
            result = search(a, title, label, format)
            if results.count > 0:
                return result

    elif '/' in artist:
        print("No records found, possible multiple artists...")
        for a in artist.split('/'):
            result = search(a, title, label, format)
            if results.count > 0:
                return result

    if '&' in artist or '/' in artist:
        results = discogs.search(artist=artist, format=format, label=label, type='release')
        if results.count == 0:
            results = discogs.search(artist=artist, format='Vinyl', type='release')
        if results.count > 0:
            return results

    return discogs.search(artist=artist, release_title=title, format='Vinyl', type='release')


def find_version(results, record):
    scored = [(score_result(result, record), result) for result in results]
    max_score = max([s[0] for s in scored])

    best = []
    for s in scored:
        print(str(s[0]) + ' = ' + str(s[1].id))
        if s[0] == max_score:
            best.append(s[1])

    best_best = None
    best_score = -1
    for b in best:
        score = 0 if b.notes is None else SequenceMatcher(None, b.notes, record['Comments']).ratio()
        if score > best_score:
            best_score = score
            best_best = b

    return best_best


def score_result(result, record):
    label_score = 0
    if result.labels:
        for label in result.labels:
            score = SequenceMatcher(None, label.name, record['Label']).ratio()
            if score > label_score:
                label_score = score

    # year_diff = abs(result.year - int(record['Year'])) / 10

    artists = ' / '.join([a.name for a in result.artists])
    return SequenceMatcher(None, ' / '.join(artists), record['Artist']).ratio() \
        + SequenceMatcher(None, result.title, record['Title']).ratio() \
        + label_score  # - year_diff


def log(log_file, message, err=False):
    if err:
        error(message)
        log_file.write('### ' + message + ' ###\n')
    else:
        print(message)
        log_file.write(message + '\n')


with open("nerddisco.log", "w") as log_file:
    for record in parse_records(csv_path):
        if record['Status'] != 'Wanted':
            log(log_file, '\nSearching for ' + str(record))
            results = search(record['Artist'], record['Title'], record['Label'], record['Type'])

            num = len(results) if type(results) is list else results.count
            if num == 0:
                log(log_file, 'No results found', True)
            else:
                release = find_version(results, record)
                log(log_file, str(num) + ' results, using ' + str(release.id))

                url = discogs._base_url + '/users/' + username + '/collection/folders/1/releases/' + str(release.id)
                discogs._post(url, None)

        log_file.flush()
        os.fsync(log_file)
