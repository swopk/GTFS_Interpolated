# Code and data for "Temporal Resolution and Interpolation of Inter-Stop Travel Times in GTFS Bus Schedules"

The top-level files are the code and data as submitted, kept unchanged as the release `submitted-2026-09-14`:
- `screening.py` ran the whole submitted analysis in one file.
- `feed_metadata.csv` gives the versioned download URL and SHA-256 hash of every catalog entry.
- `feed_data.csv` holds the submitted measurements, one row per analyzed feed (1,865).
- `feed_failures.csv` lists the 1,217 excluded feeds with the reason. Together with `feed_data.csv`, it gives the 3,082 feeds kept after deduplication.
- `attrition.csv` gives the counts in the selection flow.

The revised analysis is in `Code/` and `data_files/`, and reads the top-level files where it needs them. The scripts download GTFS from their versioned Mobility Database URLs and check each against its SHA-256 hash.

## Steps and files
1. **Deduplication** (`Code/deduplicate_feeds_v2.py`, the same code as in `screening.py`). Working from the full catalog download, it keeps one representative feed per network. Its output is the list of 3,082 representatives in `feed_data.csv` and `feed_failures.csv`. It needs all 3,890 downloaded feeds, so the checks below start from its output.
2. **Download** (`Code/download_selected_v2.py`). Downloads the 3,082 representatives and checks their hashes.
3. **Measurement** (`Code/remeasure_feeds_v11.py`). Runs `measure_feed_v2.py` on every representative and writes one row per analyzed feed to `data_files/feed_data_v2.csv`.
4. **Statistics** (`data_files/paper_numbers.xlsx`). Sheet `Table&Findings` calculates all numbers used in the text. 
5. **Figures** (`Code/figures/`). Three R scripts draw Figures 1 to 3 from the data files.

```
Code/
  settings_v2.py             thresholds, time windows and file locations used by all scripts
  deduplicate_feeds_v2.py    keeps one representative feed per network (step 1)
  download_selected_v2.py    downloads the 3,082 representatives and checks their SHA-256 hashes
  remeasure_feeds_v11.py     runs measure_feed_v2.py on every representative and writes data_files/feed_data_v2.csv
  measure_feed_v2.py         measures one feed, using the four files below, and returns its row
  read_feed_v2.py            reads a feed, picks the analyzed weekday and selects its bus or rail trips
  travel_times_v2.py         inter-stop travel times and whole-minute shares (question i)
  interpolation_test_v2.py   straight-line test of stop times between timepoints (question ii)
  peak_offpeak_v2.py         peak-versus-midday comparison for bus and segregated modes (question iii)
  figures/
    prisma_v17.R             Figure 1: feed selection flow
    resolution_v17.R         Figure 2: share of inter-stop travel times on a whole minute
    decoupling_v17.R         Figure 3: share of stop times flagged approximate against sub-minute precision
data_files/
  feed_data_v2.csv           the same 1,865 feeds measured by the revised code
  paper_numbers.xlsx         all final calculations using excel formula on feed_data_v2.csv
```
The suffixes in file names (`_v2`, `_v11`, `_v17`) are internal revision labels.

## Requirements
- Python 3.10 or newer, with `pandas`, `numpy` and `requests` (`pip install pandas numpy requests`).
- R 4.x (base graphics only) for the figures.
- Excel 2013 or later for the statistics.
- About 18 GB of disk space for a full run.

## Checking the work

### 1. Numbers
Open `data_files/paper_numbers.xlsx`. Sheet `Table 1` lists each number with its 95% CI and the number of feeds behind it. Shares use the Wald interval and medians the order-statistic interval.

### 2. Test run on four feeds
```bash
cd Code
python download_selected_v2.py --ids mdb-1121 mdb-1189 mdb-2099 mdb-1294
python remeasure_feeds_v11.py --ids mdb-1121 mdb-1189 mdb-2099 mdb-1294
```
This writes `data_files/feed_data_v2_test.csv`. Its four rows match the rows with the same `feed_id` in `data_files/feed_data_v2.csv`, which are also the rows on sheet `feed_data_v2` of the workbook. 

The four feeds are:
- Knoxville: whole minutes;
- Blacksburg: seconds from interpolation;
- Sibiu: whole minutes with a fixed 10-s dwell;
- Rome: bus and metro.

### 3. Full run 
```bash
cd Code
python download_selected_v2.py
python remeasure_feeds_v11.py --workers 4
```
This rewrites `data_files/feed_data_v2.csv`.
- If a feed's versioned URL no longer works, the download falls back to the agency URL. The feed is reported as failed if the hash does not match.
- If the run stops, the same command resumes it.
- To recompute the numbers, paste the new `feed_data_v2.csv` over sheet `feed_data_v2` of the workbook, starting at cell A1.

### 4. Figures
```bash
cd Code/figures
Rscript prisma_v17.R
Rscript resolution_v17.R
Rscript decoupling_v17.R
```
Each script writes its figure as PDF and JPEG into `Code/figures/`.
