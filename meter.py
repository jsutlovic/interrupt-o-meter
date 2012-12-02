from flask import Flask, render_template, request, abort
from pyquery import PyQuery as pq
from datetime import date, datetime, time
import shelve
import json
import os
import sys
import logging

app = Flask(__name__)

DATA_FILE = 'meter'
SHELF = shelve.open(DATA_FILE, writeback=True)
DEBUG = 'DEBUG' in os.environ or 'dev' in sys.argv
DATE_FORMAT = '%Y/%m/%d %H:%M:%S %Z'
POINT_KEY_MAP = {
    'done': ['accepted'],
    'started': ['delivered', 'started'],
    'planned': ['unstarted'],
    'icebox': ['unscheduled']
}

logging.basicConfig(level=logging.INFO if DEBUG else logging.WARN)


def merge_iom_data(new, old):
    """
    Zips values of two dictionaries together, with new values paired with 0
    and old values paired with 1
    """

    return dict(
        (k, v) for (k, v) in
        zip(
            new.keys(),
            zip(
                zip([0] * len(new.values()), new.values()),
                zip([1] * len(old.values()), old.values())
            )
        )
    )


def get_keys_totals(keysmap, data):
    """
    Map data in one formatted dictionary to another
    """
    result = {}

    for key, datakeys in keysmap.items():
        result[key] = sum([data.get(datakey, 0) for datakey in datakeys])

    return result


def parse_pivotal_xml(xml):
    """
    Get meaningful information out of Pivotal XML data
    """
    stories = pq(xml)

    current_date = datetime.combine(SHELF['current_iteration'], time())
    last_date = datetime.combine(SHELF['last_iteration'], time())

    current_points = {}
    last_points = {}

    for story in stories("story"):
        s = pq(story)
        story_data = {}
        story_data['date'] = datetime.strptime(s.children("created_at").text(),
                                               DATE_FORMAT)
        story_data['state'] = s.children("current_state").text()

        if s.children('estimate'):
            try:
                estimate = int(s.children('estimate').text())
                points = max(estimate, 1)
            except ValueError:
                points = 1
            finally:
                logging.info("Estimate: %d, points: %d" % (estimate, points))
        else:
            logging.info("No estimate, 1 point")
            points = 1

        story_data['points'] = points

        if story_data.get('date') > current_date:
            data_dict = current_points
        elif story_data.get('date') > last_date:
            data_dict = last_points
        else:
            data_dict = None

        if data_dict is not None:
            state = story_data['state']
            data_dict[state] = data_dict.get(state, 0) + story_data['points']

    current_data = get_keys_totals(POINT_KEY_MAP, current_points)
    last_data = get_keys_totals(POINT_KEY_MAP, last_points)

    return current_data, last_data


def update_meter_data():
    # Get data from pivotal
    # process data
    # set data to SHELF
    raise NotImplemented


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

    SHELF['current_iteration_data'] = {
        'done': 3,
        'started': 2,
        'planned': 4,
        'icebox': 1
    }

    iom_data = merge_iom_data(SHELF['current_iteration_data'],
                              SHELF['last_iteration_data'])
    iom_data = json.dumps(iom_data)

    days_since = json.dumps(days_since_data)
    return render_template('index.html',
                           days_since=days_since,
                           iom_data=iom_data)


def setup_db():
    """
    Provides some basic initial data for the app
    """
    SHELF['last_outage'] = date(2012, 11, 24)
    SHELF['max_outage'] = 0

    SHELF['last_hotfix'] = date(2012, 11, 23)
    SHELF['max_hotfix'] = 0

    SHELF['current_iteration'] = date(2012, 11, 12)
    SHELF['current_iteration_data'] = get_keys_totals(POINT_KEY_MAP, {})

    SHELF['last_iteration'] = date(2012, 10, 26)
    SHELF['last_iteration_data'] = get_keys_totals(POINT_KEY_MAP, {})

    # Finished setup, so we're set up
    SHELF['setup'] = True
    SHELF.sync()


if __name__ == '__main__':
    if not 'setup' in SHELF or DEBUG:
        setup_db()

    port = os.environ.get('PORT', 8084)
    try:
        port = int(port)
    except ValueError:
        logging.error('Invalid port: %s' % port)

    logging.info("Settings:")
    logging.info("Debug: %s" % DEBUG)
    logging.info("Port: %d" % port)
    app.run(host='0.0.0.0', port=port, debug=DEBUG)
