from flask import Flask, render_template, request, abort
from pyquery import PyQuery as pq
from datetime import date, datetime
import shelve
import json
import os
import sys

app = Flask(__name__)

DATA_FILE = 'meter'
SHELF = shelve.open(DATA_FILE, writeback=True)
DEBUG = 'dev' in os.environ or 'dev' in sys.argv
DATE_FORMAT = '%Y/%m/%d %H:%M:%S %Z'


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


def parse_pivotal_xml(xml):
    stories = pq(xml)
    for story in stories("story"):
        s = pq(story)

        print s.children("current_state").text()
        print s.children("created_at")
        print datetime.strptime(s.children("created_at").text(), DATE_FORMAT)
        print "====="


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'reset' in request.form:
            if request.form.get('reset') == 'hotfix':
                last_outage = 0
                SHELF['last_hotfix'] = date.today()
                SHELF.sync()
                return "OK"

            elif request.form.get('reset') == 'outage':
                last_hotfix = 0
                SHELF['last_outage'] = date.today()
                SHELF.sync()
                return "OK"

            elif request.form.get('reset') == 'iteration':
                return "Reset iteration!"

        abort(400)

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


def setup_db():
    """
    Provides some basic initial data for the app
    """
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
    SHELF.sync()


if __name__ == '__main__':
    if not SHELF.has_key('setup') or DEBUG:
        setup_db()

    port = os.environ.get('PORT', 8084)
    try:
        port = int(port)
    except ValueError:
        print 'Invalid port: %s' % port

    print "Settings:"
    print "Debug: %s" % DEBUG
    print "Port: %d" % port
    app.run(host='0.0.0.0', port=port, debug=DEBUG)
