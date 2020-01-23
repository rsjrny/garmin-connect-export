#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
File: gcexport.py
Original author: Kyle Krafka (https://github.com/kjkjava/)
Date: April 28, 2015
Fork author: Michael P (https://github.com/moderation/)
Date: August 25, 2018
Updates: Russ Lilley
Date: May 12, 2019
Updates: Thomas Th.
Date: Jan 20, 2020
Description:    Use this script to export your fitness data from Garmin Connect.
                See README.md for more information.



"""

####################################################################################################################
# Updates:
# rsjrny    22 May 2019 Replaced verbose print with logging
# rsjrny    13 May 2019 Added --verbose and --debug ARGS
# rsjrny    13 may 2019 Added -JSON [y , n] to keep or delete the JSON and CSV files
# rsjrny    13 May 2019 Added a delay between files to eliminated http timeouts and file in use conditions
# rsjrny    13 May 2019 Fixed the fit_filename so the skip already downloaded would work
# rsjrny    13 May 2019 Moved various functions to the gceutils.py file
# telemaxx  20.Jan 2020 Fixed Fenix bug, runs now on win and linux, new --workflowdirectory ARGS
####################################################################################################################


import argparse
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from getpass import getpass
from os import mkdir, remove, stat
from os.path import isdir, isfile, sep, join
from shutil import copyfile
from subprocess import call
from sys import argv
from xml.dom.minidom import parseString

import gceaccess
import gceargs
import gceutils

log = logging.getLogger()
logging.basicConfig()
SCRIPT_VERSION = "1.0.0"
CURRENT_DATE = datetime.now().strftime("%Y-%m-%d")
ACTIVITIES_DIRECTORY = "." + sep + CURRENT_DATE + "_garmin_connect_export"
TOTAL_TO_DOWNLOAD = 0
TOTAL_DOWNLOADED = 0
TOTAL_COPIED = 0
TOTAL_SKIPPED = 0
TOTAL_RETRIEVED = 0

# define the ARGs
PARSER = argparse.ArgumentParser()
gceargs.addargs(PARSER, ACTIVITIES_DIRECTORY)
ARGS = PARSER.parse_args()

if ARGS.debug:
    log.setLevel(logging.DEBUG)

if ARGS.version:
    print(argv[0] + ", version " + SCRIPT_VERSION)
    sys.exit(0)

USERNAME = ARGS.username if ARGS.username else input("Username: ")
PASSWORD = ARGS.password if ARGS.password else getpass()


def getallfiles():
    # If the user wants to download all activities, query the userstats
    # on the profile page to know how many are available
    user_stats = gceaccess.query_garmin_stats()
    # Persist JSON
    gceutils.write_to_file(ARGS.directory + sep + "userstats.json", user_stats.decode(), "a")
    # Modify total_to_download based on how many activities the server reports.
    json_user = json.loads(user_stats)
    return int(json_user["userMetrics"][0]["totalActivities"])


def downloadfile(actid):
    """
    Download the file from the garmin site in the requested format. If the file already exists
    in the directory the return value is 1 else the download url, filemode and filename are returned
    :param actid:
    :return:
    """
    fitfilename = ""
    tcxfilename = ""
    gpxfilename = ""
    if ARGS.format == "gpx":
        datafilename = (ARGS.directory + sep + actid + "_activity.gpx")
        downloadurl = gceaccess.URL_GC_GPX_ACTIVITY + actid + "?full=true"
        log.debug("DownloadURL: " + downloadurl)
        filemode = "w"
    elif ARGS.format == "tcx":
        datafilename = (ARGS.directory + sep + actid + "_activity.tcx")
        downloadurl = gceaccess.URL_GC_TCX_ACTIVITY + actid + "?full=true"
        log.debug("DownloadURL: " + downloadurl)
        filemode = "w"
    else:
        # some original files may not contain a .fit file. They may only have extracted a gpx or tcx
        # so we want to check for all types here.
        datafilename = (ARGS.directory + sep + actid + "_activity.zip")
        fitfilename = (ARGS.directory + sep + actid + ".fit")
        tcxfilename = (ARGS.directory + sep + actid + ".tcx")
        gpxfilename = (ARGS.directory + sep + actid + ".gpx")
        downloadurl = gceaccess.URL_GC_ORIGINAL_ACTIVITY + actid
        log.debug("DownloadURL: " + downloadurl)
        filemode = "wb"

    if ARGS.format != "original" and isfile(datafilename):
        print("\tData file already exists; skipping...")
        return 1, 1, 1

    # Regardless of unzip setting, don't redownload if the ZIP or FIT file exists.
    # some original files only contain tcx or gpx - check for all types before downloading
    if ARGS.format == "original" \
            and (isfile(datafilename)
                 or isfile(fitfilename)
                 or isfile(tcxfilename)
                 or isfile(gpxfilename)):
        print("\tFIT data file already exists; skipping...")
        return 1, 1, 1

    return downloadurl, filemode, datafilename


def finalizefiles(data, data_filename):
    """
    Finalize the datfile processing. If we are using format gpx see if we have tracks. If we are using
    original and the unzip option was selected unzip the file and remove the original file

    """
    global TOTAL_COPIED
    if ARGS.format == "gpx" and data:
        # Validate GPX data. If we have an activity without GPS data (e.g., running on a
        # treadmill), Garmin Connect still kicks out a GPX (sometimes), but there is only
        # activity information, no GPS data. N.B. You can omit the XML parse (and the
        # associated log messages) to speed things up.
        gpx = parseString(data)
        if gpx.getElementsByTagName("trkpt"):
            gceutils.printverbose(ARGS.verbose, "Done. GPX data saved.")
        else:
            gceutils.printverbose(ARGS.verbose, "Done. No track points found.")
    elif ARGS.format == "original":
        # Even manual upload of a GPX file is zipped, but we'll validate the extension.
        if ARGS.unzip and data_filename[-3:].lower() == "zip":
            gceutils.printverbose(ARGS.verbose, "Unzipping and removing original files...")
            try:
                gceutils.printverbose(ARGS.verbose, "Filesize is: " + str(stat(data_filename).st_size))
            except Exception as ferror:
                print("Unable to determine file stats for " + data_filename + "Error: " + str(ferror))
                return
            if stat(data_filename).st_size > 0:
                zip_file = open(data_filename, "rb")
                z = zipfile.ZipFile(zip_file)
                for name in z.namelist():
                    z.extract(name, ARGS.directory)
                    log.debug("extracting file: " + ARGS.directory + sep + name) 
                    if len(ARGS.workflowdirectory) and join(ARGS.directory, name) != join(ARGS.workflowdirectory, name):
                        copyfile(join(ARGS.directory, name), join(ARGS.workflowdirectory, name))
                        log.debug("copy file to: " + ARGS.workflowdirectory + sep + name)  
                        TOTAL_COPIED += 1
                zip_file.close()
            else:
                gceutils.printverbose(ARGS.verbose, "Skipping 0Kb zip file.")
            remove(data_filename)
        gceutils.printverbose(ARGS.verbose, "Done, getting next file")
        time.sleep(3)
    else:
        gceutils.printverbose(ARGS.verbose, "Done, getting next file.")


def processactivity(alist):
    global TOTAL_SKIPPED, TOTAL_RETRIEVED
    for a in alist:
        # create a string from the activity to avoid having to use the str function multiple times.
        stractid = str(a["activityId"])
        # Display which entry we're working on.
        print("Garmin Connect activity: [" + stractid + "]  " + str(a["activityName"]))
        # download the file from Garmin
        download_url, file_mode, data_filename = downloadfile(stractid)
        # if the file already existed go get the next file
        if download_url == 1:
            TOTAL_SKIPPED += 1
            continue
        # extract the data from the downloaded file
        data = gceaccess.download_data(download_url, ARGS.format)
        # if the original zip has no data
        if data == "":
            print("/tempty file, no data existed in the downloaded file")
            continue
        
        TOTAL_RETRIEVED += 1
        # write the file
        gceutils.write_to_file(data_filename, gceutils.decoding_decider(ARGS.format, data), file_mode)
        log.debug("Activity summary URL: " + gceaccess.URL_GC_ACTIVITY + stractid)
        # get the summary info, if unavailable go get next file
        try:
            activity_summary = gceaccess.http_req(gceaccess.URL_GC_ACTIVITY + stractid)
        except Exception as aerror:
            print("unable to get activity " + str(aerror))
            continue
        # write the summary file
        gceutils.write_to_file(ARGS.directory + sep + stractid + "_activity_summary.json",
                               activity_summary.decode(), "a", )
        # build the json format files
        json_summary, json_gear, json_device, json_detail = gceaccess.createjson(ARGS.directory,
                                                                                 stractid, activity_summary)
        # CSV_FILE.write(csv_record)
        CSV_FILE.write(gceaccess.buildcsvrecord(a, json_summary, json_gear, json_device, json_detail))
        finalizefiles(data, data_filename)


print("Welcome to Garmin Connect Exporter!")

# Create directory for data files.
if isdir(ARGS.directory):
    print(
        "Warning: Output directory already exists. Will skip already-downloaded files and \
append to the CSV file."
    )

try:
    gceaccess.gclogin(USERNAME, PASSWORD)
except Exception as error:
    print(error)
    sys.exit(8)

# create the activities directory if it is not there
if not isdir(ARGS.directory):
    mkdir(ARGS.directory)
    
if len(ARGS.workflowdirectory):
    if not isdir(ARGS.workflowdirectory):
        mkdir(ARGS.workflowdirectory)

CSV_FILENAME = ARGS.directory + sep + "activities.csv"
CSV_EXISTED = isfile(CSV_FILENAME)
CSV_FILE = open(CSV_FILENAME, "a", encoding="utf-8")
if not CSV_EXISTED:
    CSV_FILE.write(gceaccess.csvheader())

if ARGS.count == "all":
    TOTAL_TO_DOWNLOAD = getallfiles()
else:
    TOTAL_TO_DOWNLOAD = int(ARGS.count)

print("Total to download: " + str(TOTAL_TO_DOWNLOAD))

# This while loop will download data from the server in multiple chunks, if necessary.
while TOTAL_DOWNLOADED < TOTAL_TO_DOWNLOAD:
    # Maximum chunk size 'limit_maximum' ... 400 return status if over maximum.  So download
    # maximum or whatever remains if less than maximum.
    # As of 2018-03-06 I get return status 500 if over maximum
    if TOTAL_TO_DOWNLOAD - TOTAL_DOWNLOADED > gceaccess.LIMIT_MAXIMUM:
        NUM_TO_DOWNLOAD = gceaccess.LIMIT_MAXIMUM
    else:
        NUM_TO_DOWNLOAD = TOTAL_TO_DOWNLOAD - TOTAL_DOWNLOADED

    gceutils.printverbose(ARGS.verbose, "Number left to download = " + str(NUM_TO_DOWNLOAD))

    search_parms = {"start": TOTAL_DOWNLOADED, "limit": NUM_TO_DOWNLOAD}
    log.debug("Search parms" + str(search_parms))

    # Query Garmin Connect
    log.debug("Activity list URL: " + gceaccess.URL_GC_LIST + urllib.parse.urlencode(search_parms))
    activity_list = gceaccess.http_req(gceaccess.URL_GC_LIST + urllib.parse.urlencode(search_parms))
    gceutils.write_to_file(ARGS.directory + sep + "activity_list.json", activity_list.decode(), "a")

    processactivity(json.loads(activity_list))
    TOTAL_DOWNLOADED += NUM_TO_DOWNLOAD
# End while loop for multiple chunks.

CSV_FILE.close()

# delete the json and csv files before archiving. If requested
if ARGS.delete is not None:
    print("deleting types " + str(ARGS.delete) + " from the output directory")
    gceutils.removefiles(ARGS.directory, ARGS.delete)

# archive the downloaded files
if ARGS.archive:
    print("archiving the downloaded files to: " + ARGS.archive)
    gceutils.zipfilesindir(ARGS.archive, ARGS.directory)

# print the final counts
print("Total Requested...." + str(TOTAL_TO_DOWNLOAD))
print("Total Downloaded..." + str(TOTAL_RETRIEVED))
print("Total Copied......." + str(TOTAL_COPIED))
print("Total Skipped......" + str(TOTAL_SKIPPED))

# open the csv file in an external program if requested
if len(ARGS.external):
    print("Open CSV output: " + CSV_FILENAME)
    # open CSV file. Comment this line out if you don't want this behavior
    call([ARGS.external, "--" + ARGS.args, CSV_FILENAME])

print("Done!")
