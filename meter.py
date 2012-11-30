from flask import Flask, render_template, request
from datetime import date
import shelve
import json
import os
import sys

app = Flask(__name__)

DATA_FILE = 'meter'
SHELF = shelve.open(DATA_FILE, writeback=True)
DEBUG = 'dev' in os.environ or 'dev' in sys.argv


def merge_iom_data(new, old):
    return dict(
            (k, v) for (k, v) in
            zip(
                new.keys(),
                zip(
                    zip([0]*4, new.values()),
                    zip([1]*4, old.values())
                )
            )
        )


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'reset_outage' in request.form:
            print "Reset Outage!"

        elif 'reset_hotfix' in request.form:
            print "Reset Hotfix!"

        elif 'reset_iteration' in request.form:
            print "Reset iteration!"

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

    current_data = {
        'done': 3,
        'started': 2,
        'planned': 4,
        'icebox': 1
    }

    iom_data = merge_iom_data(current_data, SHELF['last_iteration_data'])
    iom_data = json.dumps(iom_data)

    days_since = json.dumps(days_since_data)
    return render_template('index.html', days_since=days_since, iom_data=iom_data)


def setup():
    """
    Provides some basic initial data for the app
    """
    SHELF['create_date'] = date.today()

    SHELF['last_outage'] = date(2012, 11, 24)
    SHELF['max_outage'] = 0

    SHELF['last_hotfix'] = date(2012, 11, 23)
    SHELF['max_hotfix'] = 0

    SHELF['current_iteration'] = date(2012, 11, 12)
    SHELF['last_iteration_data'] = {
        'done': 0,
        'started': 0,
        'planned': 0,
        'icebox': 0
    }

    # Finished setup, so we're set up
    SHELF['setup'] = True


if __name__ == '__main__':
    if not SHELF.has_key('setup'):
        setup()

    port = os.environ.get('PORT', 8084)
    try:
        port = int(port)
    except ValueError:
        print 'Invalid port: %s' % port

    print "Settings:"
    print "Debug: %s" % DEBUG
    print "Port: %d" % port
    app.run(host='0.0.0.0', port=port, debug=DEBUG)
