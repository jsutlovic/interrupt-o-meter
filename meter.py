from flask import Flask, render_template
from datetime import date
import shelve
import json

app = Flask(__name__)

DATA_FILE = 'meter'
SHELF = shelve.open(DATA_FILE, writeback=True)


@app.route('/')
def index():
    last_outage = (date.today() - SHELF['last_outage']).days
    if last_outage > SHELF['max_outage']:
        SHELF['max_outage'] = last_outage
        SHELF.sync()

    max_outage = SHELF['max_outage']

    last_hotfix = (date.today() - SHELF['last_hotfix']).days
    if last_hotfix > SHELF['max_hotfix']:
        SHELF['max_hotfix'] = last_hotfix
        SHELF.sync()

    max_hotfix = SHELF['max_hotfix']

    days_since_data = {
        'outage': {
            'current': last_outage,
            'max': max_outage
        },
        'hotfix': {
            'current': last_hotfix,
            'max': max_hotfix
        }
    }

    days_since = json.dumps(days_since_data)
    return render_template('index.html', days_since=days_since)


def setup():
    """
    Provides some basic initial data for the app
    """
    SHELF['create_date'] = date.today()

    SHELF['last_outage'] = date(2012, 11, 24)
    SHELF['max_outage'] = 0

    SHELF['last_hotfix'] = date(2012, 11, 23)
    SHELF['max_hotfix'] = 0

    # Finished setup, so we're set up
    SHELF['setup'] = True


if __name__ == '__main__':
    if not SHELF.has_key('setup'):
        setup()

    app.run(host='0.0.0.0', port=8084, debug=True)