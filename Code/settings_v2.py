# Thresholds, time windows and file locations used by all scripts.
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data_files")
MANIFEST = os.path.join(DATA_DIR, "manifest.csv")
PROVENANCE = os.path.join(HERE, "..", "feed_metadata.csv")
FEEDS_DIR = os.environ.get("GTFS_FEEDS_DIR", os.path.join(HERE, "..", "feeds"))
OUT_DIR = DATA_DIR
PUBLISHED = os.path.join(HERE, "..", "feed_data.csv")
PUBLISHED_FAILURES = os.path.join(HERE, "..", "feed_failures.csv")

BUS_TYPES = {"3", "11", "700", "702", "704", "705", "710", "711", "712", "713", "714", "715"}
CONTROL_TYPES = {"0", "1", "2", "900", "901", "400", "401", "402", "100", "101", "102"}
AM = (7 * 3600, 9 * 3600)
PM = (16 * 3600, 18 * 3600)
MIDDAY = (10 * 3600, 14 * 3600)
MIN_TRIPS_PER_CELL = 3
MIN_CONTROL_SEGMENTS = 20
MIN_BUS_TRIPS = 50
MIN_RUNTIMES = 20
MAX_RUNTIME = 3600
PREFERRED_WEEKDAYS = {1, 2, 3}
LINE_TOL_S = 1.5

STOP_JACCARD_THRESHOLD = 0.50
MIN_SHARED_STOPS = 25
MIN_STOPS_FOR_OVERLAP = 50
NAME_PROXIMITY_KM = 5.0
MAX_PROVIDERS_PER_URL = 3
MAX_PROVIDERS_PER_CLUSTER = 4
MAX_PROVIDERS_PER_STOP_ID = 3
URL_JACCARD_THRESHOLD = 0.50
AGGREGATOR_MIN_AGENCIES = 5
STATUS_RANK = {"active": 0, "valid": 0, "unspecified": 1, "": 1,
               "future": 2, "inactive": 3, "deprecated": 4}

STOP_WORDS = {"transit", "transportation", "authority", "district", "regional",
              "public", "bus", "buses", "metro", "metropolitan", "county", "city",
              "of", "the", "system", "services", "service", "agency", "department",
              "transportes", "transporte", "trafik", "verkehr", "mobilite",
              "mobilites", "reseau", "transports", "transport"}
