from os.path import isfile
from pandas import read_csv, read_fwf, concat, Timedelta
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
    onidata = read_fwf('https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt')
    #onidata = read_fwf('./snow/oni.ascii.txt')
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
    
#Define a series of functions to be used to calculate the desired statistics on all stations
#and all years of data. I'll probably write these individually outside of the functions first
#and then when I am satisfied that they work okay, will place them inside the functions. Still
#don't know how to effectively debug functions in python and especially not in Jupyter lab.
def process_snow_maxima(df):
    '''
    Take the snow data frame as input and process for the timing and amplitude of peak snow for all stations
    and for all years. Output will be a dataframe with index of years and columns of stations containing max
    snow amount and a second data frame with the same organization but containing timing of max snow.
    '''
    pass

def process_snowoff_day(df):
    '''
    Take the snow data frame as input and process for the timing of the snowpack's demise. Output will be a
    pandas dataframe with an index of years and columns per station with values of the hydrological day of year of
    snowpack loss.
    '''
    pass

def process_peak_snowmelt(df):
    '''
    Take the snow data frame as input and process for the amplitude and timing of the peak in snow melt rate.
    This will be noisy and will amplify data errors as it involves the calculation of a differrence series
    and finding the largest negative value of that series. Data jumps will be preferentially selcted for.
    Output will be two data frames with index of years and columns for stations with values of hydrological
    day of year of the peak melt rate and the value of that peak rate.
    '''
    pass
