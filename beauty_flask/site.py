from flask import (
    Blueprint, flash, render_template, g, session, request, redirect, url_for, jsonify, make_response, current_app
)

import os.path
from dateutil import tz
from datetime import datetime, timedelta
import json

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .extensions import cache, mail
from flask_mail import Message

# Constants needed for calculating datetimes
DAYS = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')
TIMEBLOCKS = ('0800', '0830', '0900', '0930', '1000', '1030', '1100', '1130', '1200', '1230', '1300', '1330', '1400', '1430', '1500', '1530', '1600', '1630', '1700', '1730', '1800', '1830', '1900', '1930', '2000')
BOOKING_LEN = timedelta(hours=1)


bp = Blueprint('site', __name__)

@bp.route('/')
def index():
    return render_template('site/index.html')


@bp.route('/pay')
def pay():
    return render_template('site/pay.html')

@bp.route('/contact')
def contact():
    return render_template('site/contact.html')

#--------------------------------------------------------------------------------------------------#
#                                      Booking Functionality                                       #
#--------------------------------------------------------------------------------------------------#

def connectToCalendar():
    """
    Connect to Google Calendar via the service account
    Returns the connection Resource service
    """
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly', 'https://www.googleapis.com/auth/calendar.events']
    SVC_ACCT_FILE = 'instance/beauty-svc-acct.json'
    if os.path.exists(SVC_ACCT_FILE):
        creds = service_account.Credentials.from_service_account_file(SVC_ACCT_FILE, scopes = SCOPES)
    return build('calendar', 'v3', credentials=creds)
    

def getCalendarTimezone(service):
    cal = service.calendars().get(calendarId='onspl2i87fputjkjg8h0uhhmno@group.calendar.google.com').execute()
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
#    if session.get('offset') is None:
#        flash("Unexpected error while trying to get available sessions")
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


def confirmationEmail():
    """
    Send email confirmation to client
    """
#    with app.app_context():
    msg = Message("Appointment Confirmation with Stephanie Beauty")
    msg.recipients= [session['clientEmail']]
    msg.html = "<head><style>body {background-color: #FFF6F5; padding: 10px;}</style></head><body>"
    msg.html += ""
    msg.html += "<h1 style=\"font-style:italic; text-decoration:underline;\">You're booked!</h1>"
    msg.html += "<h2>Custom Makeup Session</h2>"
    msg.html += "<p>" + session['apptDate'] + "</p>"
    msg.html += "<p>" + session['apptTime']['start'] + " &ndash; " + session['apptTime']['end'] + "</p>"
    msg.html += "<p><a href=\"" + url_for('site.booked', apptID=session['apptID'])  + "\">"
    msg.html += "To cancel or reschedule, use this link</a></p></body>"
    mail.send(msg)
    return


#--------------------------------------------------------------------------------------------------#
#                                          Booking Views                                           #
#--------------------------------------------------------------------------------------------------#

@bp.route('/openings')
def openings():
    """
    This view is only ever accessed by JavaScript fetch from the 'book' page
    Gets the available openings for a week and sends them JSONed
    """
    # Connect to calendar or fail gracefully (directing user to Contact Me page)
    ## Get service from cache, or renew
    service = cache.get("service") 
    if service is None: # service not created yet or is expired
        try:
            service = connectToCalendar()
            cache.set("service", service)
            current_app.logger.debug("Successfully connected to service")
        except Exception as e:
#            g.error = True
#            return redirect(url_for('site.book'))
#            return jsonify(error = e);
            current_app.logger.info("Error while connecting to calendar to get service")
            current_app.logger.error(e)
            pass
    else:
        current_app.logger.debug("Got service from cache")

     # Get the calendar's timezone and save in the various forms needed
    if session.get('tzStr') is None or session.get('tzName') is None:
        try: # try to query calendar
            tzName = getCalendarTimezone(service) # the IANA timezone name e.g. 'America/Chicago'
            session['tzName'] = tzName
            current_app.logger.debug("Successfully got timezone info from calendar")
        except Exception as e: # default to Central time if the query fails
            tzName = 'America/Chicago'
            session['tzName'] = tzName
            current_app.logger.info("Error while getting timezone info from calender")
            current_app.logger.error(e)
        # Save most human-friendly name for output
        tzStrs = {'CDT':'Central Daylight Time', 'CST':'Central Standard Time'}
        ltz = datetime.now().astimezone().strftime('%Z')
        if ltz in tzStrs and tzName == 'America/Chicago':
            session['tzStr'] = tzStrs[ltz]
        else: 
            session['tzStr'] = "the " + tzName + " timezone"
    
    # Get offset from session
    offset = session.get('offset')
    ## Default to 0 if this fails
    if offset is None:
        offset = 0    

    # Get the week's information and its openings
    ## Use cached values if available, otherwise query again and save
    week = cache.get("week_{}".format(offset))
    openings = cache.get("openings_{}".format(offset))
    if week is None or openings is None:
        try:
            week, openings = getOpeningsForWeek(service)
        except Exception as e:
#            g.error = True
#            return redirect(url_for('site.book'))
            current_app.logger.info("Error while getting the openings")
            current_app.logger.error(e)
            return jsonify(error=e);
#            pass
        else:
            cache.set("week_{}".format(offset), week)
            cache.set("openings_{}".format(offset), openings)

### Practice values ###
#     g.error = False
#    week = {'Sun': ['May', '09'], 'Mon': ['May', '10'], 'Tue': ['May', '11'], 'Wed': ['May', '12'], 'Thu': ['May', '13'], 'Fri': ['May', '14'], 'Sat': ['May', '15']}
#    openings = {'Sun': ['1700', '1900', '1930', '2000'], 'Mon': ['1700', '1730', '1800', '1830', '1900', '1930', '2000'], 'Tue': ['1700', '1730', '1800', '1830', '1900', '1930', '2000'], 'Wed': ['1700', '1730', '1800', '1830', '1900', '1930', '2000'], 'Thu': ['1700', '1730', '1800', '1830', '1900', '1930', '2000'], 'Fri': ['1830', '1900', '1930', '2000'], 'Sat': ['0900', '0930', '1000', '1030', '1400', '1430', '1500', '1530', '1600', '1630', '1700', '1730', '1800', '1830', '1900', '1930', '2000']}

    return jsonify(week=week, openings=openings)

# Alternative way to respond with make_response
#    headers = {"Content-Type": "application/json"}
##               "Access-Control-Allow-Origin": "*"}
#    return make_response({'hey':'Test response!'}, 200, headers) 


@bp.route('/book', methods=['POST'])
def bookPost():
    # 'POST' was to book an appointment
    if request.form.get('booking'):
        appt = request.form.get('booking')
        apptDT = datetime.strptime("{}_{}_{}".format('2021', appt, '00'), '%Y_%b_%d_%H%M_%S')
        session['apptDT'] = apptDT # save to session
        return redirect(url_for('site.booking'))
    
    # 'POST' was to scroll through the schedule
    ## Update the offset based on 'POST', then redirect to base page
    if session.get('offset') is None:
        session['offset'] = 0
        current_app.logger.debug("book POST, offset not in session")
    elif request.form.get('next'):
        session['offset'] = session.get('offset') + 1
        current_app.logger.debug("book POST, next")
    elif request.form.get('prev'):
        if session['offset'] > 0: # safety to never go below 0
            session['offset'] = session.get('offset') - 1
        current_app.logger.debug("book POST, prev")
    offset = session['offset']
    current_app.logger.debug("offset {}".format(offset))

    return redirect(url_for('site.book'))


@bp.route('/book', methods=['GET'])
def book():
    """
    Main landing page for Booking an appointment
    Search through available sessions and book an appointment
    """
    return render_template('site/book.html', days=DAYS, timeblocks=TIMEBLOCKS)


@bp.route('/booking', methods=['GET'])
def booking():
    """
    After use has selected an appointment time, allow them to confirm it or go back
    """
    # Datetime object for the appointment
    apptDT = session['apptDT']

    # Craft human-friendly appointment date and times
    dStr = {1: 'st', 2: 'nd', 3: 'rd', 4: 'th', 5: 'th', 6: 'th', 7: 'th', 8: 'th', 9: 'th', 0: 'th'}
    apptDate = apptDT.strftime("%A, %B %d") + dStr[int(apptDT.strftime("%d")[1])]
    apptTime = {'start' : apptDT.strftime("%I:%M").lstrip('0')+apptDT.strftime("%p").lower(),
                'end': (apptDT + BOOKING_LEN).strftime("%I:%M").lstrip('0') + (apptDT + BOOKING_LEN).strftime("%p").lower()}
    session['apptDate'] = apptDate
    session['apptTime'] = apptTime
    session.modified = True # be sure to catch apptTime dict modification

#    apptStr = apptDT.strftime("%A, %B %d") + dStr[int(apptDT.strftime("%d")[1])] + apptDT.strftime(" at %H:%M")+apptDT.strftime("%p").lower()
#    apptStr = session['appt']
    return render_template('site/booking.html', apptDate=apptDate, apptTime=apptTime)


@bp.route('/booking', methods=['POST'])
def bookingPost():
    """
    Let client confirm selected appt time, get their name and email
    """
    session['clientName'] = request.form.get('clientName')
    session['clientEmail'] = request.form.get('clientEmail')
    return redirect(url_for('site.booked'))


@bp.route('/bookAppt', methods=['GET'])
def bookAppt():
    """
    This view is only ever accessed by JavaScript fetch from the 'booked' page
    Book appointment on calendar for given date and time
    """
    # Get the service to connect to calendar
    service = cache.get("service") 
    if service is None: # service not created yet or is expired
        try:
            service = connectToCalendar()
            cache.set("service", service)
            current_app.logger.debug("Successfully connected to service")
        except Exception as e:
            current_app.logger.info("Error while connecting to calendar to get service")
            current_app.logger.error(e)
            return redirect(url_for('site.booked'))
            pass
    else:
        current_app.logger.debug("Got service from cache")

    # Craft the event
    event = {
        'summary': "Session with {}".format(session['clientName']),
        'description': "Session with {}; {}".format(session['clientName'], session['clientEmail']),
        'start': { 'dateTime': session['apptDT'].isoformat(), 'timeZone': session['tzName'] },
        'end': { 'dateTime': (session['apptDT']+BOOKING_LEN).isoformat(), 'timeZone': session['tzName'] }
    }

    # Connect to calendar and create the event
    try:
        event = service.events().insert(calendarId='onspl2i87fputjkjg8h0uhhmno@group.calendar.google.com', 
                                        body=event).execute()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error="Error while creating appointment event.")

    # If event was successfully created, send confirmation email and show confirmation on page
    if event.get('id'):
        session['apptID'] = event['id']
        try:
            confirmationEmail()
            return jsonify(apptID=session['apptID'])
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(apptID=session['apptID'], emailError="Error while sending email.")
    else:
        return jsonify(error="Error while creating appointment event.")


@bp.route('/booked', methods=['GET'])
def booked():
    """
    When the user has confirmed their appointment selection, serve this page
    """
    return render_template('site/booked.html', apptDate=session['apptDate'], apptTime=session['apptTime'])


@bp.route('/booked/<apptID>', methods=['GET'])
def changeAppt(apptID):
    """
    Allow a user to change or cancel their appointment
    """
    return
