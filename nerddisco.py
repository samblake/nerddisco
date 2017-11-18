from __future__ import print_function
from difflib import SequenceMatcher
import sys
import discogs_client
import csv
import re

csv_path = sys.argv[1]
token = sys.argv[2]

nonalphanumeric = re.compile('[^a-zA-Z\d\s:]')

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
    results = discogs.search(
        artist=nonalphanumeric.sub('', artist),  # remove non-alphanumeric, the API can't handle them
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
    best = []
    max_score = -1
    for result in results:
        score = score_result(result, record)
        print(score)
        if score > max_score:
            max_score = score

    for result in results:
        score = score_result(result, record)
        if score == max_score:
            best.append(result)

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
    if result.labels is not None:
        for label in result.labels:
            score = SequenceMatcher(None, label.name, record['Label']).ratio()
            if score > label_score:
                label_score = score

    # year_diff = abs(result.year - int(record['Year'])) / 10

    artists = ' / '.join([a.name for a in result.artists])
    return SequenceMatcher(None, ' / '.join(artists), record['Artist']).ratio() \
        + SequenceMatcher(None, result.title, record['Title']).ratio() \
        + label_score  # - year_diff


for record in parse_records(csv_path):
    if record['Status'] != 'Wanted':
        print('\nSearching for ' + str(record))
        results = search(record['Artist'], record['Title'], record['Label'], record['Type'])

        if results.count == 0:
            error("No results found")
        else:
            print(str(results.count) + ' results')
            release = find_version(results, record)
            print(release)
