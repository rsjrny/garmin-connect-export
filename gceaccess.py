"""

garmin.com access for exporting data files


"""

import http.cookiejar
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from os.path import sep

import gceutils

log = logging.getLogger(__name__)

LIMIT_MAXIMUM = 1000


def query_garmin_stats():
    log.debug("Getting display name and user stats via: " + URL_GC_PROFILE)
    profile_page = http_req(URL_GC_PROFILE).decode()
    # write_to_file(args.directory + '/profile.html', profile_page, 'a')
    # extract the display name from the profile page, it should be in there as
    # \"displayName\":\"eschep\"
    pattern = re.compile(
        r".*\\\"displayName\\\":\\\"([-.\w]+)\\\".*", re.MULTILINE | re.DOTALL
    )
    match = pattern.match(profile_page)
    if not match:
        raise Exception("Did not find the display name in the profile page.")
    display_name = match.group(1)
    log.info("displayName=" + display_name)
    log.info(URL_GC_USERSTATS + display_name)
    user_stats = http_req(URL_GC_USERSTATS + display_name)
    log.debug("Finished display name and user stats ~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    return user_stats


def download_data(download_url, formattype):
    # Download the data file from Garmin Connect. If the download fails (e.g., due to timeout),
    # this script will die, but nothing will have been written to disk about this activity, so
    # just running it again should pick up where it left off.
    log.info("\tDownloading file...")
    data = ""
    try:
        data = http_req(download_url)
    except urllib.error.HTTPError as errs:
        # Handle expected (though unfortunate) error codes; die on unexpected ones.
        if errs.code == 500 and formattype == "tcx":
            # Garmin will give an internal server error (HTTP 500) when downloading TCX files
            # if the original was a manual GPX upload. Writing an empty file prevents this file
            # from being redownloaded, similar to the way GPX files are saved even when there
            # are no tracks. One could be generated here, but that's a bit much. Use the GPX
            # format if you want actual data in every file, as I believe Garmin provides a GPX
            # file for every activity.
            log.info("\t\tWriting empty file since Garmin did not generate a TCX file for this activity...")
            data = ""
        elif errs.code == 404 and formattype == "original":
            # For manual activities (i.e., entered in online without a file upload), there is
            # no original file. # Write an empty file to prevent redownloading it.
            log.info("\t\tWriting empty file since there was no original activity data...")
            data = ""
        else:
            raise Exception("Failed. Got an unexpected HTTP error (" + str(errs.code) + download_url + ").")
    finally:
        return data


def gclogin(username, password):
    # DATA = gceaccess.builddata()
    # log.debug(urllib.parse.urlencode(DATA))
    # Initially, we need to get a valid session cookie, so we pull the login page.
    log.debug("Request login page")
    http_req(URL_GC_LOGIN)
    log.debug("Finish login page")
    # Now we'll actually login.
    # Fields that are passed in a typical Garmin login.
    post_data = {
        "username": username,
        "password": password,
        "embed": "false",
        "rememberme": "on",
    }
    headers = {"referer": URL_GC_LOGIN}
    log.debug("Post login data")
    login_response = http_req(URL_GC_LOGIN + "#", post_data, headers).decode()
    log.debug("Finish login post")
    # extract the ticket from the login response
    pattern = re.compile(r".*\?ticket=([-\w]+)\";.*", re.MULTILINE | re.DOTALL)
    match = pattern.match(login_response)

    if not match:
        log.debug("the pattern and match do not match")
        log.debug("login response = " + str(login_response))
        raise Exception(
            "Did not get a ticket in the login response. Cannot log in. "
            "Did you enter the correct username and password?"
        )
    login_ticket = match.group(1)
    log.debug("Login ticket=" + login_ticket)
    log.debug("Request authentication URL: " + URL_GC_POST_AUTH + "ticket=" + login_ticket)
    # login to garmin
    http_req(URL_GC_POST_AUTH + "ticket=" + login_ticket)
    log.debug("Finished authentication")


def http_req(url, post=None, headers=None):
    """Helper function that makes the HTTP requests."""
    request = urllib.request.Request(url)
    # Tell Garmin we're some supported browser.
    request.add_header(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, \
        like Gecko) Chrome/54.0.2816.0 Safari/537.36",
    )
    if headers:
        for header_key, header_value in headers.items():
            request.add_header(header_key, header_value)
    if post:
        post = urllib.parse.urlencode(post)
        post = post.encode("utf-8")  # Convert dictionary to POST parameter string.
    # print("request.headers: " + str(request.headers) + " COOKIE_JAR: " + str(COOKIE_JAR))
    # print("post: " + str(post) + "request: " + str(request))
    response = OPENER.open(request, data=post)

    if response.getcode() == 204:
        # For activities without GPS coordinates, there is no GPX download (204 = no content).
        # Write an empty file to prevent redownloading it.
        log.info("Writing empty file since there was no GPX activity data...")
        return ""
    elif response.getcode() != 200:
        raise Exception("Bad return code (" + str(response.getcode()) + ") for: " + url)
    # print(response.getcode())

    return response.read()


def createjson(directory, stractId, actsum):
    json_summary = json.loads(actsum)
    log.debug(json_summary)
    log.debug("Device detail URL: " + URL_DEVICE_DETAIL
              + str(json_summary["metadataDTO"]["deviceApplicationInstallationId"]))
    device_detail = http_req(
        URL_DEVICE_DETAIL
        + str(json_summary["metadataDTO"]["deviceApplicationInstallationId"])
    )
    if device_detail:
        gceutils.write_to_file(
            directory + sep + stractId + "_app_info.json",
            device_detail.decode(), "a",
        )
        json_device = json.loads(device_detail)
        log.debug(json_device)
    else:
        log.debug("Retrieving Device Details failed.")
        json_device = None
    log.debug("Activity details URL: " + URL_GC_ACTIVITY + stractId + "/details")
    try:
        activity_detail = http_req(
            URL_GC_ACTIVITY + stractId + "/details"
        )
        gceutils.write_to_file(
            directory + sep + stractId + "_activity_detail.json",
            activity_detail.decode(), "a",
        )
        json_detail = json.loads(activity_detail)
        log.debug(json_detail)
    except Exception as error:
        print("Retrieving Activity Details failed. Reason: " + str(error))
        json_detail = None
    log.debug("Gear details URL: " + URL_GEAR_DETAIL + "activityId=" + stractId)
    gear_detail = http_req(URL_GEAR_DETAIL + "activityId=" + stractId)
    try:
        gceutils.write_to_file(directory + sep + stractId + "_gear_detail.json",
                               gear_detail.decode(),
                               "a", )
        json_gear = json.loads(gear_detail)
        log.debug(json_gear)
    except Exception as error:
        print("Retrieving Gear Details failed. Error: " + str(error))
        json_gear = None

    return json_summary, json_gear, json_device, json_detail


def buildcsvrecord(a, json_summary, json_gear, json_device, json_detail):
    # Write stats to CSV.
    empty_record = ","
    csv_record = ""
    csv_record += (
        empty_record
        if "activityName" not in a or not a["activityName"]
        else '"' + a["activityName"].replace('"', '""') + '",'
    )
    # maybe a more elegant way of coding this but need to handle description as null
    if "description" not in a:
        csv_record += empty_record
    elif a["description"] is not None:
        csv_record += '"' + a["description"].replace('"', '""') + '",'
    else:
        csv_record += empty_record
    # Gear detail returned as an array so pick the first one
    csv_record += (
        empty_record
        if not json_gear or "customMakeModel" not in json_gear[0]
        else json_gear[0]["customMakeModel"] + ","
    )
    csv_record += (
        empty_record
        if "startTimeLocal" not in json_summary["summaryDTO"]
        else '"' + json_summary["summaryDTO"]["startTimeLocal"] + '",'
    )
    csv_record += (
        empty_record
        if "elapsedDuration" not in json_summary["summaryDTO"]
        else gceutils.hhmmss_from_seconds(json_summary["summaryDTO"]["elapsedDuration"]) + ","
    )
    csv_record += (
        empty_record
        if "movingDuration" not in json_summary["summaryDTO"]
        else gceutils.hhmmss_from_seconds(json_summary["summaryDTO"]["movingDuration"]) + ","
    )
    csv_record += (
        empty_record
        if "distance" not in json_summary["summaryDTO"]
        else "{0:.5f}".format(json_summary["summaryDTO"]["distance"] / 1000) + ","
    )
    csv_record += (
        empty_record
        if "averageSpeed" not in json_summary["summaryDTO"]
        else gceutils.kmh_from_mps(json_summary["summaryDTO"]["averageSpeed"]) + ","
    )
    csv_record += (
        empty_record
        if "averageMovingSpeed" not in json_summary["summaryDTO"]
        else gceutils.kmh_from_mps(json_summary["summaryDTO"]["averageMovingSpeed"]) + ","
    )
    csv_record += (
        empty_record
        if "maxSpeed" not in json_summary["summaryDTO"]
        else gceutils.kmh_from_mps(json_summary["summaryDTO"]["maxSpeed"]) + ","
    )
    csv_record += (
        empty_record
        if "elevationLoss" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["elevationLoss"]) + ","
    )
    csv_record += (
        empty_record
        if "elevationGain" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["elevationGain"]) + ","
    )
    csv_record += (
        empty_record
        if "minElevation" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["minElevation"]) + ","
    )
    csv_record += (
        empty_record
        if "maxElevation" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["maxElevation"]) + ","
    )
    csv_record += empty_record if "minHR" not in json_summary["summaryDTO"] else ","
    csv_record += (
        empty_record
        if "maxHR" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["maxHR"]) + ","
    )
    csv_record += (
        empty_record
        if "averageHR" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["averageHR"]) + ","
    )
    csv_record += (
        empty_record
        if "calories" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["calories"]) + ","
    )
    csv_record += (
        empty_record
        if "averageBikeCadence" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["averageBikeCadence"]) + ","
    )
    csv_record += (
        empty_record
        if "maxBikeCadence" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["maxBikeCadence"]) + ","
    )
    csv_record += (
        empty_record
        if "totalNumberOfStrokes" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["totalNumberOfStrokes"]) + ","
    )
    csv_record += (
        empty_record
        if "averageTemperature" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["averageTemperature"]) + ","
    )
    csv_record += (
        empty_record
        if "minTemperature" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["minTemperature"]) + ","
    )
    csv_record += (
        empty_record
        if "maxTemperature" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["maxTemperature"]) + ","
    )
    csv_record += (
        empty_record
        if "activityId" not in a
        else '"https://connect.garmin.com/modern/activity/'
             + str(a["activityId"])
             + '",'
    )
    csv_record += (
        empty_record if "endTimestamp" not in json_summary["summaryDTO"] else ","
    )
    csv_record += (
        empty_record if "beginTimestamp" not in json_summary["summaryDTO"] else ","
    )
    csv_record += (
        empty_record if "endTimestamp" not in json_summary["summaryDTO"] else ","
    )
    csv_record += (
        empty_record
        if not json_device or "productDisplayName" not in json_device
        else json_device["productDisplayName"].replace('\u0113','e') + " " + json_device["versionString"] + ","
    )
    csv_record += (
        empty_record
        if "activityType" not in a
        else a["activityType"]["typeKey"].title() + ","
    )
    csv_record += (
        empty_record
        if "eventType" not in a
        else a["eventType"]["typeKey"].title() + ","
    )
    csv_record += (
        empty_record
        if "timeZoneUnitDTO" not in json_summary
        else json_summary["timeZoneUnitDTO"]["timeZone"] + ","
    )
    csv_record += (
        empty_record
        if "startLatitude" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["startLatitude"]) + ","
    )
    csv_record += (
        empty_record
        if "startLongitude" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["startLongitude"]) + ","
    )
    csv_record += (
        empty_record
        if "endLatitude" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["endLatitude"]) + ","
    )
    csv_record += (
        empty_record
        if "endLongitude" not in json_summary["summaryDTO"]
        else str(json_summary["summaryDTO"]["endLongitude"]) + ","
    )
    csv_record += (
        empty_record
        if "gainCorrectedElevation" not in json_summary["summaryDTO"]
        else ","
    )
    csv_record += (
        empty_record
        if "lossCorrectedElevation" not in json_summary["summaryDTO"]
        else ","
    )
    csv_record += (
        empty_record
        if "maxCorrectedElevation" not in json_summary["summaryDTO"]
        else ","
    )
    csv_record += (
        empty_record
        if "minCorrectedElevation" not in json_summary["summaryDTO"]
        else ","
    )
    csv_record += (
        empty_record
        if not json_detail or "metricsCount" not in json_detail
        else str(json_detail["metricsCount"]) + ","
    )
    csv_record += "\n"

    return csv_record


def csvheader():
    header = "Activity name,\
Description,\
Bike,\
Begin timestamp,\
Duration (h:m:s),\
Moving duration (h:m:s),\
Distance (km),\
Average speed (km/h),\
Average moving speed (km/h),\
Max. speed (km/h),\
Elevation loss uncorrected (m),\
Elevation gain uncorrected (m),\
Elevation min. uncorrected (m),\
Elevation max. uncorrected (m),\
Min. heart rate (bpm),\
Max. heart rate (bpm),\
Average heart rate (bpm),\
Calories,\
Avg. cadence (rpm),\
Max. cadence (rpm),\
Strokes,\
Avg. temp (°C),\
Min. temp (°C),\
Max. temp (°C),\
Map,\
End timestamp,\
Begin timestamp (ms),\
End timestamp (ms),\
Device,\
Activity type,\
Event type,\
Time zone,\
Begin latitude (°DD),\
Begin longitude (°DD),\
End latitude (°DD),\
End longitude (°DD),\
Elevation gain corrected (m),\
Elevation loss corrected (m),\
Elevation max. corrected (m),\
Elevation min. corrected (m),\
Sample count\n"
    return header


def buildFriendlyFilename(a, json_summary, json_gear, json_device, json_detail, ARGS):
    """
    crerates a friendly, readable string for the filename in workflowmode
    """
    empty_record = ""
    seperator = "-"
    file_name = ""
    
    file_name += (
        empty_record
        if "startTimeLocal" not in json_summary["summaryDTO"]
        else json_summary["summaryDTO"]["startTimeLocal"][:19].replace(':','-')
    )
    file_name += seperator
    file_name += (
        empty_record
        if "activityName" not in a or not a["activityName"]
        else re.compile('[^a-zA-Z0-9_-]').subn('_', a["activityName"])[0][:30]
    )
    file_name += seperator
    file_name += (
        empty_record
        if not json_device or "productDisplayName" not in json_device
        else re.compile('[^a-zA-Z0-9_-]').subn('_', json_device["productDisplayName"].replace('\u0113','e'))[0][:12]
    )  
    file_name += seperator
    file_name += (
        empty_record
        if "elevationGain" not in json_summary["summaryDTO"]
        else "%dhm" % (json_summary["summaryDTO"]["elevationGain"])
    )
    
    file_name += '.fit'
    file_name = file_name.replace('-.fit','.fit')

#    gceutils.printverbose(ARGS.verbose, 'Friendly name: ' + file_name)
    return file_name

COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIE_JAR))
WEBHOST = "https://connect.garmin.com"
REDIRECT = "https://connect.garmin.com/modern/"
BASE_URL = "https://connect.garmin.com/en-US/signin"
SSO = "https://sso.garmin.com/sso"
CSS = "https://static.garmincdn.com/com.garmin.connect/ui/css/gauth-custom-v1.2-min.css"

DATA = {
    "service": REDIRECT,
    "webhost": WEBHOST,
    "source": BASE_URL,
    "redirectAfterAccountLoginUrl": REDIRECT,
    "redirectAfterAccountCreationUrl": REDIRECT,
    "gauthHost": SSO,
    "locale": "en_US",
    "id": "gauth-widget",
    "cssUrl": CSS,
    "clientId": "GarminConnect",
    "rememberMeShown": "true",
    "rememberMeChecked": "false",
    "createAccountShown": "true",
    "openCreateAccount": "false",
    "displayNameShown": "false",
    "consumeServiceTicket": "false",
    "initialFocus": "true",
    "embedWidget": "false",
    "generateExtraServiceTicket": "true",
    "generateTwoExtraServiceTickets": "false",
    "generateNoServiceTicket": "false",
    "globalOptInShown": "true",
    "globalOptInChecked": "false",
    "mobile": "false",
    "connectLegalTerms": "true",
    "locationPromptShown": "true",
    "showPassword": "true",
}

# URLs for various services.
URL_GC_LOGIN = "https://sso.garmin.com/sso/signin?" + urllib.parse.urlencode(DATA)
URL_GC_POST_AUTH = "https://connect.garmin.com/modern/activities?"
URL_GC_PROFILE = "https://connect.garmin.com/modern/profile"
URL_GC_USERSTATS = "https://connect.garmin.com/modern/proxy/userstats-service/statistics/"
URL_GC_LIST = "https://connect.garmin.com/modern/proxy/activitylist-service/activities/search/activities?"
URL_GC_ACTIVITY = "https://connect.garmin.com/modern/proxy/activity-service/activity/"
URL_GC_GPX_ACTIVITY = "https://connect.garmin.com/modern/proxy/download-service/export/gpx/activity/"
URL_GC_TCX_ACTIVITY = "https://connect.garmin.com/modern/proxy/download-service/export/tcx/activity/"
URL_GC_ORIGINAL_ACTIVITY = "http://connect.garmin.com/proxy/download-service/files/activity/"
URL_DEVICE_DETAIL = "https://connect.garmin.com/modern/proxy/device-service/deviceservice/app-info/"
URL_GEAR_DETAIL = "https://connect.garmin.com/modern/proxy/gear-service/gear/filterGear?"
