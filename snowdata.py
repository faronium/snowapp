from os.path import isfile
from pandas import read_csv, read_fwf, concat, Timedelta, DataFrame
import pandas as pd
import numpy as np

def get_snow_archive(localfilename=None):
    #One possible filename: ./snow/SW_DailyArchive.csv
    #Here the [0] tells fxn to parse first column into an index
    if localfilename is None:
        dfarch = read_csv('https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/SW_DailyArchive.csv',index_col=[0],parse_dates=[0]) 
    else:
        if isfile(localfilename):
            dfarch = read_csv(localfilename,index_col=[0],parse_dates=[0])
        else:
            raise FileNotFoundError(f'File {localfilename} could not be found')
    
    return dfarch

def get_fresh_snow(localfilename=None):
    #One possible filename:  ./snow/SWDaily.csv
    if localfilename is None:
        dffresh = read_csv('https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/SWDaily.csv',index_col=[0],parse_dates=[0])
    else:
        if isfile(localfilename):
            dffresh = read_csv(localfilename,index_col=[0],parse_dates=[0])
        else:
            raise FileNotFoundError(f'File {localfilename} could not be found')

    return dffresh

def load_munge_snow_data():
    # Try to load from local files first, fall back to remote if not available
    import os
    if os.path.exists('./snow/SW_DailyArchive.csv') and os.path.exists('./snow/SWDaily.csv'):
        dfarch = get_snow_archive('./snow/SW_DailyArchive.csv')
        dffresh = get_fresh_snow('./snow/SWDaily.csv')
    else:
        dfarch = get_snow_archive()
        dffresh = get_fresh_snow()
    df = concat([dfarch,dffresh],axis=0)

    #Check current year's data for entries with all na/no data
    if (dffresh.isna().sum() == len(dffresh)).any():
        #Have stations with all rows of na, must subset dffresh to remove those stations.
        print('hi')
        stations_with_current_year = dffresh.columns[~(dffresh.isna().sum() == len(dffresh))]
    else:
        stations_with_current_year = dffresh.columns[~(dffresh.isna().sum() == len(dffresh))]

    # ## Munging data to consistent timestamps and getting some useful indexes
    '''
    Looks like there are stations that have data at a non-standard time of 16:00. Six stations that have 
    data on the even hour at some point in their record. These are '1A02P McBride Upper', '1B02P Tahtsa Lake', 
    '1B08P Mt. Pondosy', '2F18P Brenda Mine', '3A25P Squamish River Upper', '3A28P Tetrahedron'. In all of 
    these stations, the hourly data is in addition to the data reported at 16:00. So, can safely drop all 
    of the excess data without worry.
    '''
    #Deal with the non-daily observations. Most are on the 16:00, some are on the 00:00 and others are on the even hour.
    #Set the rows with hours != 16:00 to NaN for stations '1A02P McBride Upper', '1B02P Tahtsa Lake', '1B08P Mt. Pondosy', '2F18P Brenda Mine',
    #         '3A25P Squamish River Upper', '3A28P Tetrahedron']
    df.loc[df.index.strftime('%H').isin(['00','01','02','03','04','05','06','07','08','09','10','11',
            '12','13','14','15','17','18','19','20','21','22','23']),
            ['1A02P McBride Upper', '1B02P Tahtsa Lake', '1B08P Mt. Pondosy', '2F18P Brenda Mine',
             '3A25P Squamish River Upper', '3A28P Tetrahedron']] = np.nan

    ''' Additionally, the stations '4D16P Forrest Kerr Mid Elevation Snow', '4D17P Forrest Kerr High Elevation Snow' 
    have data on the 00:00. These also appear not to have data on the 16:00. So, perhaps we can simply move those 
    timestamps by the 16 hours to make them
    '''
    dfsub = df[['4D16P Forrest Kerr Mid Elevation Snow','4D17P Forrest Kerr High Elevation Snow']]
    dfsub = dfsub.dropna(axis=0,how='all')
    dfsub.index += Timedelta("16 hours")
    
    # Now simply merge the two data frames into a master data frame that only has the data we want.
    df.loc[df.index.strftime('%H') == '22',~df.columns.isin(['4D16P Forrest Kerr Mid Elevation Snow','4D17P Forrest Kerr High Elevation Snow'])] = np.nan
    df = df.loc[:,~df.columns.isin(['4D16P Forrest Kerr Mid Elevation Snow','4D17P Forrest Kerr High Elevation Snow'])].join(dfsub)
    df = df.dropna(axis=0,how='all')
    df = df.loc[:,df.columns.sort_values().unique()]

    return df, stations_with_current_year

#Import oceanic Nino index and massage into a form that allows selection by ENSO strength
def get_wyear_extrema_oni():
    import os
    # Try local file first
    if os.path.exists('./snow/oni.ascii.txt'):
        onidata = read_fwf('./snow/oni.ascii.txt')
    else:
        onidata = read_fwf('https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt')
    oniseaslist = list(['OND','NDJ','DJF','JFM','FMA','MAM'])
    onidata = onidata[onidata['SEAS'].isin(oniseaslist)]
    #Need to add a year to the OND and NDJ seasoned years to correspond to the hydrological year that ENSO cycle belongs to.
    onidata['YR'] = onidata['YR'].mask(onidata['SEAS'].isin(['OND','NDJ']),onidata['YR']+1)


    #Issue here is that the selector finds the years where the ONI range was met, but needs
    #To identify the peak ONI values during the snow year.
    mnxonidata = onidata.groupby(['YR']).min()
    mnxonidata['MAX_ANOM'] = onidata.groupby(['YR']).max()['ANOM']
    mnxonidata = mnxonidata.rename(columns={'ANOM':'MIN_ANOM'})
    #Three cases:
    #         1) where the min anom and the max anom are both negative, keep the min anom
    #         2) where the max anom and the min anom are both positive, keep the max anom
    #         3) where the min anom is negative and the max anom is positive, keep the largest
    #                absolute value and it's sign.
    minminmap = (mnxonidata['MIN_ANOM'] < 0) & (mnxonidata['MAX_ANOM'] <= 0)
    maxmaxmap = (mnxonidata['MIN_ANOM'] >= 0) & (mnxonidata['MAX_ANOM'] > 0)
    keepminmap = (mnxonidata['MIN_ANOM'] < 0) & (mnxonidata['MAX_ANOM'] > 0) & (np.abs(mnxonidata['MIN_ANOM']) >= np.abs(mnxonidata['MAX_ANOM']))
    minmap = minminmap | keepminmap
    keepmaxmap = (mnxonidata['MIN_ANOM'] < 0) & (mnxonidata['MAX_ANOM'] > 0) & (np.abs(mnxonidata['MAX_ANOM']) >= np.abs(mnxonidata['MIN_ANOM']))
    maxmap = maxmaxmap | keepmaxmap
    mnxonidata.loc[minmap,'ANOM'] = mnxonidata.loc[minmap,'MIN_ANOM']
    mnxonidata.loc[maxmap,'ANOM'] = mnxonidata.loc[maxmap,'MAX_ANOM']
    #Get most recent ONI and use this to set pick an ONI range to use in the slider initially.
    return mnxonidata

def get_oni_startrange(mnxonidata):
    if mnxonidata.loc[mnxonidata.index[(len(mnxonidata)-1)],"ANOM"] > 0.5:
        return [0.5,3]
    elif mnxonidata.loc[mnxonidata.index[(len(mnxonidata)-1)],"ANOM"] < 0.5:
        return [-3,-0.5]
    else:
        return [-0.5,0.5]

#Now have to find when that peak occurred...!
def count_coverage(series):
    return (~series.isna()).sum()

def get_median(series):
    return(series.median())
#Define a series of functions to be used to calculate the desired statistics on all stations
#and all years of data. I'll probably write these individually outside of the functions first
#and then when I am satisfied that they work okay, will place them inside the functions. Still
#don't know how to effectively debug functions in python and especially not in Jupyter lab.
def process_snow_maxima(df):
    '''
    Take the snow data frame as input and process for the timing and amplitude of peak snow for all stations
    and for all years. Uses 5-day smoothing window to reduce noise.

    Parameters:
    -----------
    df : pandas.DataFrame
        Snow data with DatetimeIndex, columns for stations, and 'hydrological_year' and 'hydrodoy' columns

    Returns:
    --------
    peak_amount : pandas.DataFrame
        Index = hydrological years, columns = stations, values = peak SWE (mm)
    peak_timing : pandas.DataFrame
        Index = hydrological years, columns = stations, values = hydrological day of year of peak
    '''
    # Apply 5-day rolling average to smooth the data
    # Need to group by station and year to avoid smoothing across boundaries
    smoothed_data = {}
    station_cols = [col for col in df.columns if col not in ['hydrodoy', 'hydrological_year', 'month-day']]

    peak_amounts = []
    peak_timings = []
    years = df['hydrological_year'].unique()

    for year in years:
        year_data = df[df['hydrological_year'] == year].copy()
        year_peaks_amt = {}
        year_peaks_doy = {}

        for station in station_cols:
            if station in year_data.columns:
                # Apply 5-day rolling average
                smoothed = year_data[station].rolling(window=5, center=True, min_periods=3).mean()

                # Find peak
                if not smoothed.isna().all():
                    peak_idx = smoothed.idxmax()
                    year_peaks_amt[station] = smoothed[peak_idx]
                    year_peaks_doy[station] = year_data.loc[peak_idx, 'hydrodoy']
                else:
                    year_peaks_amt[station] = np.nan
                    year_peaks_doy[station] = np.nan

        peak_amounts.append(year_peaks_amt)
        peak_timings.append(year_peaks_doy)

    peak_amount = pd.DataFrame(peak_amounts, index=years)
    peak_timing = pd.DataFrame(peak_timings, index=years)

    return peak_amount, peak_timing

def process_snow_year_start(df, baseline_threshold_mm=10):
    '''
    Detect the start of the snow year using hybrid approach:
    - Calculate October baseline (mean of first 15 days)
    - Look for first sustained accumulation (positive 5-day derivative)
    - SWE must exceed baseline by threshold

    Parameters:
    -----------
    df : pandas.DataFrame
        Snow data with DatetimeIndex, columns for stations, and 'hydrological_year' and 'hydrodoy' columns
    baseline_threshold_mm : float
        Minimum SWE increase above October baseline to consider snow year started (default 10mm)

    Returns:
    --------
    snow_start_doy : pandas.DataFrame
        Index = hydrological years, columns = stations, values = hydrological day of year of snow start
    '''
    station_cols = [col for col in df.columns if col not in ['hydrodoy', 'hydrological_year', 'month-day']]
    years = df['hydrological_year'].unique()

    snow_starts = []

    for year in years:
        year_data = df[df['hydrological_year'] == year].copy()
        year_starts = {}

        for station in station_cols:
            if station in year_data.columns:
                swe = year_data[station].copy()

                # Skip if all NaN
                if swe.isna().all():
                    year_starts[station] = np.nan
                    continue

                # Calculate October baseline (first 15 days of hydro year)
                october_data = swe[year_data['hydrodoy'] <= 15]
                baseline = october_data.mean() if not october_data.isna().all() else 0

                # Calculate 5-day rolling derivative (rate of change)
                derivative = swe.diff().rolling(window=5, center=True, min_periods=3).mean()

                # Find first day where:
                # 1) derivative > 0 (accumulating)
                # 2) SWE exceeds baseline + threshold
                accumulating = derivative > 0
                above_threshold = swe > (baseline + baseline_threshold_mm)

                candidates = year_data.loc[accumulating & above_threshold, 'hydrodoy']

                if len(candidates) > 0:
                    year_starts[station] = candidates.iloc[0]
                else:
                    year_starts[station] = np.nan

        snow_starts.append(year_starts)

    snow_start_doy = pd.DataFrame(snow_starts, index=years)
    return snow_start_doy

def process_snow_year_end(df, baseline_pct_of_peak=0.05):
    '''
    Detect the end of the snow year - when SWE returns to near-baseline after peak.
    Uses percentage of seasonal peak as threshold.

    Parameters:
    -----------
    df : pandas.DataFrame
        Snow data with DatetimeIndex, columns for stations, and 'hydrological_year' and 'hydrodoy' columns
    baseline_pct_of_peak : float
        Threshold as percentage of peak SWE to consider snow year ended (default 0.05 = 5%)

    Returns:
    --------
    snow_end_doy : pandas.DataFrame
        Index = hydrological years, columns = stations, values = hydrological day of year of snow end
    '''
    station_cols = [col for col in df.columns if col not in ['hydrodoy', 'hydrological_year', 'month-day']]
    years = df['hydrological_year'].unique()

    snow_ends = []

    for year in years:
        year_data = df[df['hydrological_year'] == year].copy()
        year_ends = {}

        for station in station_cols:
            if station in year_data.columns:
                swe = year_data[station].copy()

                # Skip if all NaN
                if swe.isna().all():
                    year_ends[station] = np.nan
                    continue

                # Find peak
                peak_value = swe.max()
                if np.isnan(peak_value):
                    year_ends[station] = np.nan
                    continue

                peak_idx_pos = swe.idxmax()
                peak_doy = year_data.loc[peak_idx_pos, 'hydrodoy']

                # Look for end after peak
                after_peak = year_data[year_data['hydrodoy'] > peak_doy]
                threshold = peak_value * baseline_pct_of_peak

                # Find first day after peak where SWE drops below threshold
                below_threshold = after_peak[station] < threshold
                candidates = after_peak.loc[below_threshold, 'hydrodoy']

                if len(candidates) > 0:
                    year_ends[station] = candidates.iloc[0]
                else:
                    # Snow didn't melt by end of year
                    year_ends[station] = np.nan

        snow_ends.append(year_ends)

    snow_end_doy = pd.DataFrame(snow_ends, index=years)
    return snow_end_doy

def process_peak_snowmelt(df, melt_season_start_doy=182, melt_season_end_doy=304):
    '''
    Calculate the timing and magnitude of peak melt rate.
    Focuses on April-July period (roughly days 182-304 of hydrological year).

    Parameters:
    -----------
    df : pandas.DataFrame
        Snow data with DatetimeIndex, columns for stations, and 'hydrological_year' and 'hydrodoy' columns
    melt_season_start_doy : int
        Start of melt season in hydrological day of year (default 182 = April 1)
    melt_season_end_doy : int
        End of melt season in hydrological day of year (default 304 = July 31)

    Returns:
    --------
    peak_melt_rate : pandas.DataFrame
        Index = hydrological years, columns = stations, values = peak melt rate (mm/day, negative)
    peak_melt_timing : pandas.DataFrame
        Index = hydrological years, columns = stations, values = hydrological day of year of peak melt
    '''
    station_cols = [col for col in df.columns if col not in ['hydrodoy', 'hydrological_year', 'month-day']]
    years = df['hydrological_year'].unique()

    peak_melt_rates = []
    peak_melt_timings = []

    for year in years:
        year_data = df[df['hydrological_year'] == year].copy()
        year_melt_rates = {}
        year_melt_timings = {}

        for station in station_cols:
            if station in year_data.columns:
                # Focus on melt season only
                melt_season = year_data[
                    (year_data['hydrodoy'] >= melt_season_start_doy) &
                    (year_data['hydrodoy'] <= melt_season_end_doy)
                ].copy()

                if len(melt_season) == 0 or melt_season[station].isna().all():
                    year_melt_rates[station] = np.nan
                    year_melt_timings[station] = np.nan
                    continue

                # Calculate daily derivative (rate of change)
                derivative = melt_season[station].diff()

                # Apply 5-day smoothing to reduce noise
                smoothed_derivative = derivative.rolling(window=5, center=True, min_periods=3).mean()

                # Find maximum negative value (peak melt rate)
                if not smoothed_derivative.isna().all():
                    min_idx = smoothed_derivative.idxmin()
                    year_melt_rates[station] = smoothed_derivative[min_idx]
                    year_melt_timings[station] = melt_season.loc[min_idx, 'hydrodoy']
                else:
                    year_melt_rates[station] = np.nan
                    year_melt_timings[station] = np.nan

        peak_melt_rates.append(year_melt_rates)
        peak_melt_timings.append(year_melt_timings)

    peak_melt_rate = pd.DataFrame(peak_melt_rates, index=years)
    peak_melt_timing = pd.DataFrame(peak_melt_timings, index=years)

    return peak_melt_rate, peak_melt_timing

def process_snowoff_day(df):
    '''
    Wrapper function that calls process_snow_year_end for backwards compatibility.
    '''
    return process_snow_year_end(df)

def compute_all_indicators(df, cache_indicators=True):
    '''
    Compute all snow indicators and optionally cache them for later use.

    Parameters:
    -----------
    df : pandas.DataFrame
        Snow data with DatetimeIndex, columns for stations, and 'hydrological_year' and 'hydrodoy' columns
    cache_indicators : bool
        Whether to save computed indicators to pickle files for faster loading (default True)

    Returns:
    --------
    indicators : dict
        Dictionary containing all computed indicators:
        - 'peak_amount': Peak SWE amount (mm)
        - 'peak_timing': Day of year of peak SWE
        - 'snow_start': Day of year of snow season start
        - 'snow_end': Day of year of snow season end
        - 'peak_melt_rate': Maximum melt rate (mm/day)
        - 'peak_melt_timing': Day of year of peak melt rate
    '''
    import os
    import pickle
    from pathlib import Path

    cache_dir = Path('./snow/cache')
    cache_file = cache_dir / 'snow_indicators.pkl'

    # Try to load from cache first
    if cache_indicators and cache_file.exists():
        try:
            print("Loading cached indicators...")
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}. Recomputing...")

    print("Computing snow indicators (this may take a minute)...")

    indicators = {}

    # Compute peak snow
    print("  - Computing peak snow timing and magnitude...")
    indicators['peak_amount'], indicators['peak_timing'] = process_snow_maxima(df)

    # Compute snow year start
    print("  - Computing snow year start dates...")
    indicators['snow_start'] = process_snow_year_start(df)

    # Compute snow year end
    print("  - Computing snow year end dates...")
    indicators['snow_end'] = process_snow_year_end(df)

    # Compute peak melt rates
    print("  - Computing peak melt rates...")
    indicators['peak_melt_rate'], indicators['peak_melt_timing'] = process_peak_snowmelt(df)

    # Compute snow season length (derived indicator)
    print("  - Computing snow season lengths...")
    indicators['season_length'] = indicators['snow_end'] - indicators['snow_start']

    print("Indicator computation complete!")

    # Cache results if requested
    if cache_indicators:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'wb') as f:
                pickle.dump(indicators, f)
            print(f"Indicators cached to {cache_file}")
        except Exception as e:
            print(f"Warning: Could not cache indicators: {e}")

    return indicators
