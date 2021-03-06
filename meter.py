#!/usr/bin/env python

import os
import sys
import json
import shelve
import logging
import requests
import celeryconfig
from celery import Celery
from contextlib import closing
from pyquery import PyQuery as pq
from datetime import date, datetime, time
from dateutil.parser import parse as d_parse
from flask import Flask, render_template, request, abort


app = Flask(__name__)
celery = Celery('meter')
celery.config_from_object(celeryconfig)

# Global defs

# Environment defined
DEBUG = 'DEBUG' in os.environ or 'dev' in sys.argv
DATA_FILE = os.environ.get('DATA_FILE', 'meter.db')
TRACKER_TOKEN = os.environ.get('TRACKER_TOKEN')
PROJECT_ID = os.environ.get('PROJECT_ID')
DATE_FMT = "%Y-%m-%d"

POINT_KEY_MAP = {
    'done': ['accepted'],
    'started': ['delivered', 'started'],
    'planned': ['unstarted'],
    'icebox': ['unscheduled']
}

logging.basicConfig(level=logging.INFO if DEBUG else logging.WARN)


def get_shelf():
    return shelve.open(DATA_FILE, writeback=True)


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

    Ex2: get_keys_totals({'ab': ['a', 'b'], 'c': ['c']}, {})
    Results in: {'ab': 0, 'c': 0}
    """
    result = {}

    for key, datakeys in keysmap.items():
        result[key] = sum([data.get(datakey, 0) for datakey in datakeys])

    return result


def parse_pivotal_xml(xml):
    """
    Get meaningful information out of Pivotal XML data
    """
    with closing(get_shelf()) as shelf:
        current_date = datetime.combine(shelf['current_iteration'], time())
        last_date = datetime.combine(shelf['last_iteration'], time())

    current_points = {}
    last_points = {}
    old_points = {}

    stories = pq(xml)

    for story in stories("story"):
        s = pq(story)
        story_data = {}

        story_data['name'] = s.children('name').text()
        story_data['id'] = s.children('id').text()
        logging.debug('Story %s: %s' % (story_data['id'], story_data['name']))

        story_date = d_parse(s.children("created_at").text())
        story_data['date'] = story_date
        logging.debug('Date: %s' % story_data['date'].ctime())

        story_data['state'] = s.children("current_state").text()
        logging.debug('State: %s' % story_data['state'])

        if s.children('estimate'):
            try:
                estimate = int(s.children('estimate').text())
                points = max(estimate, 1)
            except ValueError:
                points = 1
            finally:
                logging.debug("Estimate: %d, points: %d" % (estimate, points))
        else:
            logging.debug("No estimate, 1 point")
            points = 1

        story_data['points'] = points

        if story_date >= current_date.replace(tzinfo=story_date.tzinfo):
            logging.debug('Current iteration')
            data_dict = current_points
        elif story_date >= last_date.replace(tzinfo=story_date.tzinfo):
            logging.debug('Last iteration')
            data_dict = last_points
        else:
            logging.debug('No iteration')
            data_dict = old_points

        if data_dict is not None:
            state = story_data['state']
            data_dict[state] = data_dict.get(state, 0) + story_data['points']

        logging.debug('---')

    current_data = get_keys_totals(POINT_KEY_MAP, current_points)
    last_data = get_keys_totals(POINT_KEY_MAP, last_points)
    old_data = get_keys_totals(POINT_KEY_MAP, old_points)

    return current_data, last_data, old_data


def get_pivotal_data(project, token,
                     label='interrupt', done=True, custom=None):
    """
    Pull XML data from Pivotal API, with filters

    Note: specifying custom will ignore other filters
    """

    base_url = "https://www.pivotaltracker.com/services/v3/projects/%s/stories"
    url = base_url % project
    headers = {'X-TrackerToken': token}
    filter_params = "label:\"%s\"" % label
    if done:
        filter_params += " includedone:true"
    params = {'filter': custom or filter_params}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=3)
    except Exception, error:
        logging.exception(error)
        r = None

    if r and r.status_code == 200:
        return r.content
    else:
        logging.error('Server error, status code: %s' % r.status_code)
        logging.error('Used: project: %s, token: %s' % (project, token))
        return None


def update_meter_data(project=None, token=None):
    """
    Get data from Pivotal, parse it, and shelve it
    """
    if not project:
        project = PROJECT_ID

    if not token:
        token = TRACKER_TOKEN

    pivotal_xml = get_pivotal_data(project, token)

    if not pivotal_xml:
        logging.error("Couldn't fetch data from Pivotal!")
        return False

    current_data, last_data, old_data = parse_pivotal_xml(pivotal_xml)

    logging.info("Current data: %s" % current_data)
    logging.info("Last data: %s" % last_data)
    logging.info("Old data: %s" % old_data)

    with closing(get_shelf()) as shelf:
        shelf['current_iteration_data'] = current_data
        shelf['last_iteration_data'] = last_data
        logging.debug(shelf)
        shelf.sync()

    return True


@celery.task
def tq_update_meter_data():
    update_meter_data()


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'reset' in request.form:
            if request.form.get('reset') == 'hotfix':
                last_outage = 0
                with closing(get_shelf()) as shelf:
                    shelf['last_hotfix'] = date.today()
                    shelf.sync()
                return "OK"

            elif request.form.get('reset') == 'outage':
                last_hotfix = 0
                with closing(get_shelf()) as shelf:
                    shelf['last_outage'] = date.today()
                    shelf.sync()
                return "OK"

            elif request.form.get('reset') == 'iteration':
                with closing(get_shelf()) as shelf:
                    current_iteration = date.today()
                    last_iteration = shelf['current_iteration']
                    shelf['current_iteration'] = current_iteration
                    shelf['last_iteration'] = last_iteration
                    shelf.sync()

                updated = update_meter_data()

        if 'update' in request.form:
            if request.form.get('update') == 'iteration':
                updated = update_meter_data()
                if updated:
                    #TODO: send data back
                    return "OK"
                else:
                    abort(500)

        abort(400)

    with closing(get_shelf()) as shelf:
        last_outage = (date.today() - shelf['last_outage']).days
        if last_outage > shelf['max_outage']:
            shelf['max_outage'] = last_outage
            shelf.sync()

        max_outage = shelf['max_outage']

        last_hotfix = (date.today() - shelf['last_hotfix']).days
        if last_hotfix > shelf['max_hotfix']:
            shelf['max_hotfix'] = last_hotfix
            shelf.sync()

        max_hotfix = shelf['max_hotfix']

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

        iom_data = merge_iom_data(shelf['current_iteration_data'],
                                  shelf['last_iteration_data'])
        iom_data = json.dumps(iom_data)

        days_since = json.dumps(days_since_data)

    return render_template('index.html',
                           days_since=days_since,
                           iom_data=iom_data)


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    with closing(get_shelf()) as shelf:
        dates = {
            'current': shelf['current_iteration'].strftime(DATE_FMT),
            'last': shelf['last_iteration'].strftime(DATE_FMT),
            'hotfix': shelf['last_hotfix'].strftime(DATE_FMT),
            'outage': shelf['last_outage'].strftime(DATE_FMT),
        }

        records = {
            'hotfix': shelf['max_hotfix'],
            'outage': shelf['max_outage'],
        }

        if request.method == "POST":
            logging.info(request.form)
            if 'setup' in request.form:
                dates.update({
                    'current': request.form.get(
                        'current',
                        shelf['current_iteration'].strftime(DATE_FMT)
                    ),
                    'last': request.form.get(
                        'last',
                        shelf['last_iteration'].strftime(DATE_FMT)
                    ),
                    'hotfix': request.form.get(
                        'hotfix',
                        shelf['last_hotfix'].strftime(DATE_FMT)
                    ),
                    'outage': request.form.get(
                        'outage',
                        shelf['last_outage'].strftime(DATE_FMT)
                    ),
                })

                records.update({
                    'hotfix': request.form.get(
                        'hotfix-record',
                        shelf['max_hotfix']
                    ),
                    'outage': request.form.get(
                        'outage-record',
                        shelf['max_outage']
                    ),
                })

                shelf['current_iteration'] = d_parse(dates['current']).date()
                shelf['last_iteration'] = d_parse(dates['last']).date()
                shelf['last_hotfix'] = d_parse(dates['hotfix']).date()
                shelf['last_outage'] = d_parse(dates['outage']).date()

                try:
                    shelf['max_hotfix'] = int(records['hotfix'])
                    shelf['max_outage'] = int(records['outage'])
                except ValueError:
                    abort(400)

                shelf.sync()
            else:
                abort(400)

    return render_template('setup.html', dates=dates, records=records)


def setup_db():
    """
    Provides some basic initial data for the app
    """
    with closing(get_shelf()) as shelf:
        shelf['last_outage'] = date(2012, 11, 24)
        shelf['max_outage'] = 0

        shelf['last_hotfix'] = date(2012, 11, 23)
        shelf['max_hotfix'] = 0

        shelf['current_iteration'] = date(2012, 11, 12)
        shelf['current_iteration_data'] = get_keys_totals(POINT_KEY_MAP, {})

        shelf['last_iteration'] = date(2012, 10, 26)
        shelf['last_iteration_data'] = get_keys_totals(POINT_KEY_MAP, {})

        # Finished setup, so we're set up
        shelf['setup'] = True
        shelf.sync()


if __name__ == '__main__':
    shelf = get_shelf()
    if not 'setup' in shelf or DEBUG:
        shelf.close()
        setup_db()
        update_meter_data()

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
