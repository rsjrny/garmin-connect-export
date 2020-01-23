"""
utility functions used in the garmin connect export

"""
import os.path

def addargs(parser, activities_directory):
    # global ARGS
    parser.add_argument(
        "--archive",
        help="path with filename to create/append an archive",
    )
    parser.add_argument(
        "--username",
        help="your Garmin Connect username (otherwise, you will be prompted)",
        nargs="?",
    )
    parser.add_argument(
        "--password",
        help="your Garmin Connect password (otherwise, you will be prompted)",
        nargs="?",
    )
    parser.add_argument(
        "-c",
        "--count",
        nargs="?",
        default="1",
        help="number of recent activities to download, or 'all' (default: 1)",
    )
    parser.add_argument(
        "-e",
        "--external",
        nargs="?",
        default="",
        help="path to external program to pass CSV file too (default: )",
    )
    parser.add_argument(
        "-a",
        "--args",
        nargs="?",
        default="",
        help="additional arguments to pass to external program (default: )",
    )
    parser.add_argument(
        "-f",
        "--format",
        nargs="?",
        choices=["gpx", "tcx", "original"],
        default="gpx",
        help="export format; can be 'gpx', 'tcx', or 'original' (default: 'gpx')",
    )
    parser.add_argument(
        "-d",
        "--directory",
        nargs="?",
        default=activities_directory,
        help="the directory to export to (default: './YYYY-MM-DD_garmin_connect_export')",
    )
    parser.add_argument(
        "-u",
        "--unzip",
        help="if downloading ZIP files (format: 'original'), unzip the file and removes the ZIP file",
        action="store_true",
    )
    parser.add_argument(
        "-w",
        "--workflowdirectory",
        nargs="?",
        default="",
        help="if downloading activity(format: 'original'), copy the file to this directory (default: not copying)",
    )   
    
    parser.add_argument(
        "--delete",
        nargs="*",
        help="list the .types you want deleted before the archive is created. Example --delete .csv .json.",
    )
    parser.add_argument("--debug", help="turn on debugging log", action="store_true")
    parser.add_argument("--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("--version", help="print version and exit", action="store_true")
