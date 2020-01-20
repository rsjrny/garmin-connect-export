import logging
import os
import time
from datetime import timedelta
from os import mkdir
from os.path import isdir, sep
from zipfile import ZipFile

####################################################################################################################
# Updates:
# rsjrny    13 May 2019 New file for universal functions
# telemaxx  11.January 2020 Using generic path seperator, which also works on *nix
####################################################################################################################
log = logging.getLogger(__name__)


# Zip the files from given directory that matches the filter
def zipfilesindir(dst, src):
    """
    :param dst: full path with filename where the archive will be created
    :param src: ARGS.directory - we will zip whatever is left in the directory
    :return:
    """
    log.debug("In zipfilesindir, preparing to archive all file in " + src)
    # sleep to allow system to finish processing file. We don't want an inuse or not found error
    time.sleep(3)
    dirpart = os.path.dirname(dst)
    if not isdir(dirpart):
        mkdir(dirpart)
        log.debug("Archive directory " + dirpart + "created")
    # fname = os.path.basename(dst)
    zf = ZipFile(dst, "w")
    abs_src = os.path.abspath(src)
    for dirname, subdirs, files in os.walk(src):
        for filename in files:
            absname = os.path.abspath(os.path.join(dirname, filename))
            arcname = absname[len(abs_src) + 1:]
            log.debug("zipping " + os.path.join(dirname, filename) + " as " + arcname)
            zf.write(absname, arcname)
    zf.close()
    log.info("Archive created: " + dst)


def removefiles(dirname, dellist):
    # loop thru all files in the directory
    log.debug("In removefiles preparing to delete any unwanted files based on the --delete arg")
    log.debug("   --delete arg = " + str(dellist))
    for filename in os.listdir(dirname):
        # split filename and extension.
        fname, fext = os.path.splitext(filename)
        # if this .ext is in the delete list, delete it
        if fext in dellist:
            log.debug("deleting: " + dirname + sep + filename)
            os.remove(os.path.join(dirname,filename))
    time.sleep(3)


def kmh_from_mps(mps):
    """Helper function that converts meters per second (mps) to km/h."""
    return str(mps * 3.6)


def hhmmss_from_seconds(sec):
    """Helper function that converts seconds to HH:MM:SS time format."""
    if isinstance(sec, float):
        formatted_time = str(timedelta(seconds=int(sec))).zfill(8)
    else:
        formatted_time = "0.000"
    return formatted_time


def decoding_decider(formattype, data):
    """Helper function that decides if a decoding should happen or not."""
    if formattype == "original":
        # An original file (ZIP file) is binary and not UTF-8 encoded
        data = data
    elif data:
        # GPX and TCX are textfiles and UTF-8 encoded
        data = data.decode()

    return data


def write_to_file(filename, content, mode):
    """Helper function that persists content to file."""
    if filename.endswith(".json"):
        write_file = open(filename, mode, encoding="utf-8")
    else:
        write_file = open(filename, mode)
    write_file.write(content)
    write_file.close()


def printverbose(verarg, vermsg):
    if verarg:
        print(vermsg)
    return
