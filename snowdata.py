

#Import oceanic Nino index and massage into a form that allows selection by ENSO strength
def get_wyear_extrema_oni(pd,np):
    onidata = pd.read_fwf('https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt')
    #onidata = pd.read_fwf('./snow/oni.ascii.txt')
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
