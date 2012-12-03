# Interrupt-O-Meter

Tracks interruptions and such with pretty graphs

## Configuration

#### With foreman/honcho

Create a `.env` file like this:

```bash
DEBUG=1
PORT=8084
DATA_FILE="meter.db"
TRACKER_TOKEN="abcdef12345"
PROJECT_ID="123456"
```

## Libraries used

- [Flask](http://flask.pocoo.org/)
- [Flotr2](http://www.humblesoftware.com/flotr2/) for pretty JS graphs
- [jQuery](http://jquery.com) for DOM manipulation
- [lxml](http://lxml.de/) and [pyquery](http://packages.python.org/pyquery/) for XML parsing