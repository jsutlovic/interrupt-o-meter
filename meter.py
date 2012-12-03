#!/usr/bin/env python

import os
import sys
import json
import shelve
import logging
import requests
from pyquery import PyQuery as pq
from datetime import date, datetime, time
from flask import Flask, render_template, request, abort


app = Flask(__name__)

# Global defs

# Environment defined
DEBUG = 'DEBUG' in os.environ or 'dev' in sys.argv
DATA_FILE = os.environ.get('DATA_FILE', 'meter.db')
TRACKER_TOKEN = os.environ.get('TRACKER_TOKEN')
PROJECT_ID = os.environ.get('PROJECT_ID')

SHELF = shelve.open(DATA_FILE, writeback=True)
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

    Ex: merge_iom_data({'a': 1, 'b': 0, 'c': 3}, {'a': 3, 'b': 5, 'c': -1})
    Results in: {'a': [(0, 1), (1, 3)],
                 'b': [(0, 0), (1, 5)],
                 'c': [(0, 3), (1, -1)]}
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
    Map data in one formatted dictionary to another by summing

    Ex: get_keys_totals({'ab': ['a', 'b'], 'c': ['c'], 'def': ['d', 'e', 'f']},
                        {'a': -1, 'b': 3, 'c': 8, 'd': 4, 'e': -2, 'f': 1})
    Results in: {'ab': 2, 'c': 8, 'def': 3}
    """
    result = {}

    for key, datakeys in keysmap.items():
        result[key] = sum([data.get(datakey, 0) for datakey in datakeys])

    return result


def parse_pivotal_xml(xml):
    """
    Get meaningful information out of Pivotal XML data
    """
    current_date = datetime.combine(SHELF['current_iteration'], time())
    last_date = datetime.combine(SHELF['last_iteration'], time())

    current_points = {}
    last_points = {}

    stories = pq(xml)

    for story in stories("story"):
        s = pq(story)
        story_data = {}
        story_data['date'] = datetime.strptime(s.children("created_at").text(),
                                               DATE_FORMAT)
        logging.info('Date: %s' % story_data['date'].ctime())

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

        if story_data.get('date') >= current_date:
            logging.info('Current iteration')
            data_dict = current_points
        elif story_data.get('date') >= last_date:
            logging.info('Last iteration')
            data_dict = last_points
        else:
            logging.info('No iteration')
            data_dict = None

        if data_dict is not None:
            state = story_data['state']
            data_dict[state] = data_dict.get(state, 0) + story_data['points']

        logging.info('---')

    current_data = get_keys_totals(POINT_KEY_MAP, current_points)
    last_data = get_keys_totals(POINT_KEY_MAP, last_points)

    return current_data, last_data


def get_pivotal_data(project, token, label='interrupt', includedone=True):
    base_url = "https://www.pivotaltracker.com/services/v3/projects/%s/stories"
    url = base_url % project
    headers = {'X-TrackerToken': token}
    filter_params = "label:\"%s\"" % label
    if includedone:
        filter_params += " includedone:true"
    params = {'filter': filter_params}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=0.5)
    except Exception, error:
        logging.exception(error)
        r = None

    if r and r.status_code == 200:
        return r.content
    else:
        return None


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

    logging.info("Settings:")
    logging.info("Debug: %s" % DEBUG)
    logging.info("Port: %s" % port)
    logging.info("Data file: %s" % DATA_FILE)
    logging.info("Tracker token: %s" % TRACKER_TOKEN)
    logging.info("Project ID: %s" % PROJECT_ID)

    try:
        port = int(port)
    except ValueError:
        logging.error('Invalid port: %s' % port)

    if not (TRACKER_TOKEN and PROJECT_ID):
        logging.error('Must specify TRACKER_TOKEN and PROJECT_ID')

    app.run(host='0.0.0.0', port=port, debug=DEBUG)
