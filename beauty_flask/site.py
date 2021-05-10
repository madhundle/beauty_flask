from flask import (
    Blueprint, flash, render_template, g, session, request
)

import os.path
from dateutil import tz
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import json

# Constants needed for calculating datetimes
DAYS = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')
TIMEBLOCKS = ('0800', '0830', '0900', '0930', '1000', '1030', '1100', '1130', '1200', '1230', '1300', '1330', '1400', '1430', '1500', '1530', '1600', '1630', '1700', '1730', '1800', '1830', '1900', '1930', '2000')
BOOKING_LEN = timedelta(hours=1)


bp = Blueprint('site', __name__)

@bp.route('/')
def index():
    return render_template('site/index.html')

def connectToCalendar():
    """
    Connect to Google Calendar; returns the connection Resource service
    """
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    # 
    # If I modify these scopes used, delete the instance file token.json; this
    # will force it to be recreated with the new scopes.
    # 
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

    creds = None
    if os.path.exists('/instance/token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, user must log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'instance/credentials.json', SCOPES)
            creds = flow.run_local_server(port=8088)
        # Save the credentials for the next run
        with open('instance/token.json', 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)


def getCalendarTimezone(service):
    cal = service.calendars().get(calendarId='onspl2i87fputjkjg8h0uhhmno@group.calendar.google.com').execute()
#    flash("ID: " + cal['id'])
#    flash("Summary: " + cal['summary'])
#    flash("timeZone: " + cal['timeZone'])
    return cal['timeZone']


def getEventsForWeek(service, start):
    """
    Get events from Google Calendar, from provided start datetime through end of that week
    Returns as a list of tuples of (startTime, endTime)
    Returns an empty list if there are no events in the given time frame
    """
    endDate = (start + timedelta(days=6-int(start.strftime('%w')))).date()
    end=datetime(endDate.year,endDate.month,endDate.day,23,59,59,999999,tz.gettz('America/Chicago'))
    events_result = service.events().list(calendarId='onspl2i87fputjkjg8h0uhhmno@group.calendar.google.com', 
                                          orderBy='startTime', singleEvents=True, 
                                          timeMin=start.isoformat(), timeMax=end.isoformat()).execute()

#    [(e['summary'], e['start']['dateTime'], e['end']['dateTime']) for e in events_result['items']]
    return [(e['start']['dateTime'],e['end']['dateTime']) for e in events_result['items']]

def getOpeningsForWeek(service):
    """
    From a start datetime through the end of that week, compare availability versus event conflicts
    from the calendar
    Returns that week's basic information and a dictionary of openings per day
    The start datetime is either the current datetime or the very beginning of a future week, 
    depending on the session 'offset' variable
    """
    # Create the week's info
    week = {d:[] for d in DAYS} # will store {'day': ['Mon', 'dd']} e.g. {'Sun': ['May', '09']}
    tzInfo = tz.gettz(session['tzName']) # the tzinfo type of timezone information for use with datetime

    now = datetime.now(tzInfo) 
    if session.get('offset') is None:
        flash("Error: Offset not available in getOpeningsForWeek")
    if session['offset'] == 0: # this week
        baseDateTime = now
    else: # a future week
        futureDate = (now + timedelta(weeks=session['offset'], days=-int(now.strftime('%w')))).date()
        baseDateTime = datetime(futureDate.year, futureDate.month, futureDate.day, 00, 00, 00, 000000, tzInfo)
    baseDateTimew = int(baseDateTime.strftime('%w'))

    ## process days from baseDateTime back through beginning of week
    for i in range(baseDateTimew, -1, -1):
        currday = baseDateTime - timedelta(days=baseDateTimew-i)
        week[currday.strftime('%a')] = currday.strftime('%b %d').split()

    ## process days after baseDateTime through end of week
    for i in range(baseDateTimew + 1, 7):
        currday = baseDateTime + timedelta(days=i-baseDateTimew)
        week[currday.strftime('%a')] = currday.strftime('%b %d').split()
        
    # Populate the week's openings
    ## get basic availability
    avail = {d:{t:False for t in TIMEBLOCKS} for d in DAYS} # initialize empty schedule
    if os.path.exists('instance/availability.json'): # load saved schedule
        with open('instance/availability.json', 'r') as f:
            avail = json.load(f)
#    flash("Availability:")
#    flash(avail)

    ## get potential conflicting events from schedule
    events = getEventsForWeek(service, baseDateTime) # get the events from the week in question
    events = [tuple(map(datetime.fromisoformat,e)) for e in events] # convert all to datetimes
#    flash("Events:")
#    flash(events)

    ## find openings
    openings = {} # initialize
    for i in range(baseDateTimew, 7): # from baseDateTime through the end of the week
        currDate = (baseDateTime + timedelta(days=i-baseDateTimew)).date()
        openings[currDate.strftime('%a')] = [] # initialize
        for tb in TIMEBLOCKS: # for each timeblock
            currDateTime = datetime(currDate.year, currDate.month, currDate.day, 
                                    int(tb[:2]), int(tb[2:]), 00, 000000, tzInfo)
            cDTEnd = currDateTime+BOOKING_LEN # ensure the length of a booking is free

            if currDateTime <= baseDateTime: # in the past
                continue # move on to next timeblock
            if not avail[DAYS[i]][tb]: # not available
                continue # move on to next timeblock

            conflict = False
            for eStart,eEnd in events: # check for conflicts
                if cDTEnd <= eStart: # event in the future
                    continue # not a conflict, go to next event
                elif eEnd <= currDateTime: # event in the past
                    continue # not a conflict, move on
                else: # there's a conflict
                    conflict = True
                    break

            if not conflict: # we have an opening!
                openings[currDate.strftime('%a')].append(tb)

    return week, openings

@bp.route('/book', methods=('GET', 'POST'))
def book():
    # Connect to calendar or fail gracefully (directing user to Contact Me page)
    try:
        service = connectToCalendar()
        g.error = False
    except Exception as e:
        g.error = True
        flash(e)
        return render_template('site/book.html')

    # Get the calendar's timezone and save in all the various forms I'll need to use
    if session.get('tzName') is None:
        try: # try to query calendar
            tzName = getCalendarTimezone(service) # the IANA timezone name e.g. 'America/Chicago'
        except: # default to Central time if the query fails
            session['tzName'] = 'America/Chicago' 
        else: # no exception
            session['tzName'] = tzName
    # Save a more human-friendly name for output if possible
    tzStrs = {'CDT':'Central Daylight Time', 'CST':'Central Standard Time'}
    ltz = datetime.now().astimezone().strftime('%Z')
    if ltz in tzStrs and session['tzName'] == 'America/Chicago':
        tzStr = tzStrs[ltz]
    else: 
        tzStr = "the " + tzName + " timezone"

    # Update the week offset if applicable
    if session.get('offset') is None or request.method == 'GET':
        session['offset'] = 0
    elif request.method == 'POST' and request.form.get('next'):
        session['offset'] += 1
    elif request.method == 'POST' and request.form.get('prev'):
        if session['offset'] > 0: # don't ever go below 0
            session['offset'] -= 1

    # Get the week's information and its openings
    week, openings = getOpeningsForWeek(service)

### Practice values ###
#     g.error = False
#     week = {'Sun': ['May', '09'], 'Mon': ['May', '10'], 'Tue': ['May', '11'], 'Wed': ['May', '12'], 'Thu': ['May', '13'], 'Fri': ['May', '14'], 'Sat': ['May', '15']}
#     openings = {'Sun': ['1700', '1900', '1930', '2000'], 'Mon': ['1700', '1730', '1800', '1830', '1900', '1930', '2000'], 'Tue': ['1700', '1730', '1800', '1830', '1900', '1930', '2000'], 'Wed': ['1700', '1730', '1800', '1830', '1900', '1930', '2000'], 'Thu': ['1700', '1730', '1800', '1830', '1900', '1930', '2000'], 'Fri': ['1830', '1900', '1930', '2000'], 'Sat': ['0900', '0930', '1000', '1030', '1400', '1430', '1500', '1530', '1600', '1630', '1700', '1730', '1800', '1830', '1900', '1930', '2000']}
# 
#    flash(week)    
#    flash(openings)

    # Set up values for rendering on site
    otbset = set()
    for times in openings.values():
        otbset.update(set(times))

    return render_template('site/book.html', timezone=tzStr, days=DAYS, timeblocks=sorted(list(otbset)), week=week, 
                           openings=openings)

@bp.route('/pay')
def pay():
    return render_template('site/pay.html')

@bp.route('/contact')
def contact():
    return render_template('site/contact.html')

