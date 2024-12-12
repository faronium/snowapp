#!/usr/bin/env python
# coding: utf-8

# # Snow Data
#
# Tool to import archived snow data and manipulate it using python pandas. Eventually
# to plot with plotlinkedinly/dash app of some kind.
#

# ## Importing the data

# In[2]:


import pandas as pd
import numpy as np
from dash import Dash, html, dcc, Input, Output, callback
import plotly.graph_objects as go
from datetime import datetime
from snowdata import get_wyear_extrema_oni, get_oni_startrange
from documentation import how_to_md, analysis_desc_md, header_text_md, footer_text_md
from snowmap import draw_station_map
from snowplot import snow_lineplot

'''
Author: Faron Anslow
E-mail: faron.anslow@gmail.com

This code generates a Dash web browser application that plots single station water-year snow evolution with
controls to filter by station location and ENSO state. Default is to display the median and 1-sigma range
for the entire record, the median and 1-sigma range for a selected ENSO condition and the current year's
snowpack evolution.

Future iterations will include a map-view component that will display the station locations with symbology
that illustrates the relationship between various snow statistics (such as timing of peak, amplitude of peak,
timing of peak melt, amplitude of peak melt and timing of snow loss) and seasonal teleconnection/variability
patterns.

Sources for snow data and teleconnection index values.
Snow data URL: https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/
ONI data URL: https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
PNA data URL: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.pna.monthly.b5001.current.ascii
NAO data URL: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.nao.monthly.b5001.current.ascii
All teleconnections in one! ftp://ftp.cpc.ncep.noaa.gov/wd52dg/data/indices/tele_index.nh
'''
df = pd.read_csv('./snow/SW_DailyArchive.csv',index_col=[0],parse_dates=[0]) #Here the [0] tells fxn to parse first column
#df = pd.read_csv('https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/SW_DailyArchive.csv',index_col=[0],parse_dates=[0]) #Here the [0] tells fxn to parse first column

# In[43]:



dffresh = pd.read_csv('./snow/SWDaily.csv',index_col=[0],parse_dates=[0])
#dffresh = pd.read_csv('https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/SWDaily.csv',index_col=[0],parse_dates=[0])
df = pd.concat([df,dffresh],axis=0)
#Check current data for entries with all na/no data
if (dffresh.isna().sum() == len(dffresh)).any():
    #Have stations with all rows of na, must subset dffresh to remove those stations.
    print('hi')
    stations_with_current_year = dffresh.columns[~(dffresh.isna().sum() == len(dffresh))]
else:
    stations_with_current_year = dffresh.columns[~(dffresh.isna().sum() == len(dffresh))]


# ## Munging data to consistent timestamps and getting some useful indexes
# Looks like there are stations that have data at a non-standard time of 16:00. Six stations that have data on the even hour at some point in their record. These are '1A02P McBride Upper', '1B02P Tahtsa Lake', '1B08P Mt. Pondosy', '2F18P Brenda Mine', '3A25P Squamish River Upper', '3A28P Tetrahedron'. In all of these stations, the hourly data is in addition to the data reported at 16:00. So, can safely drop all of the excess data without worry.
#Deal with the non-daily observations. Most are on the 16:00, some are on the 00:00 and others are on the even hour.
#plt.close("all")
#Set the rows with hours != 16:00 to NaN for stations '1A02P McBride Upper', '1B02P Tahtsa Lake', '1B08P Mt. Pondosy', '2F18P Brenda Mine',
#         '3A25P Squamish River Upper', '3A28P Tetrahedron']
df.loc[df.index.strftime('%H').isin(['00','01','02','03','04','05','06','07','08','09','10','11',
        '12','13','14','15','17','18','19','20','21','22','23']),
        ['1A02P McBride Upper', '1B02P Tahtsa Lake', '1B08P Mt. Pondosy', '2F18P Brenda Mine',
         '3A25P Squamish River Upper', '3A28P Tetrahedron']] = np.nan

# Additionally, the stations '4D16P Forrest Kerr Mid Elevation Snow', '4D17P Forrest Kerr High Elevation Snow' have data on the 00:00. These also appear not to have data on the 16:00. So, perhaps we can simply move those timestamps by the 16 hours to make them
dfsub = df[['4D16P Forrest Kerr Mid Elevation Snow','4D17P Forrest Kerr High Elevation Snow']]
dfsub = dfsub.dropna(axis=0,how='all')
dfsub.index += pd.Timedelta("16 hours")

# Now simply merge the two data frames into a master data frame that only has the data we want.
df.loc[df.index.strftime('%H') == '22',~df.columns.isin(['4D16P Forrest Kerr Mid Elevation Snow','4D17P Forrest Kerr High Elevation Snow'])] = np.nan
df = df.loc[:,~df.columns.isin(['4D16P Forrest Kerr Mid Elevation Snow','4D17P Forrest Kerr High Elevation Snow'])].join(dfsub)
df = df.dropna(axis=0,how='all')
df = df.loc[:,df.columns.sort_values().unique()]

#Filter the location file by what's in the data file and vice versa so that there is 1:1
#correspondence between the meta data file and the data file. Let's do this on the location ID
#locdf
datastnids = pd.Series([i.split(' ',1)[0] for i in df.columns.to_list()])
datastnnames = pd.Series([i.split(' ',1)[1] for i in df.columns.to_list()])

#Bring in the station meta data
locdf = pd.read_csv('./snow/SNW_ASWS.csv')
metastnids = locdf['LCTN_ID']
datastnnames = datastnnames[datastnids.isin(metastnids)]
datastnids = datastnids[datastnids.isin(metastnids)]
metastnids = metastnids[metastnids.isin(datastnids)]

#re-subset the dataframes so that the stations match one for one
df = df.loc[:,(datastnids+' '+datastnnames)]
locdf = locdf.loc[locdf['LCTN_ID'].isin(metastnids),:]
#if ~(stations_with_current_year.isin(datastnids+' '+datastnnames).all()):
#    raise

locdf['text'] = locdf['LCTN_ID'] + ' ' + locdf['LCTN_NM'] + '<br>Elevation: ' + (locdf['ELEVATION']).astype(str)

# Make a column formatted that gives the hydrological year. Essentially the time index, forward by 3 months,
# then reformatted to %Y using strftime.
def datetimepandas(timestamp,theformat):
    return datetime.strftime(timestamp,theformat)
def hydrodoy_from_timestamp(timestamps):
    """
    This function takes a pandas data Series object of timestamps and converts it into the day of the hydrological
    year which starts on 1 October and runs through the end of September. Returns a pandas Series of those days of year.

    Leap years are accommodated in an ugly way through making masks on the vector. I'm sure there are more elegant ways
    of doing this!
    """
    #Calculating the julian day is the first, necessary step.
    hydrodoy = timestamps.apply(datetimepandas,args=('%j',)).astype(int)
    #Next, need to link logic to operate one way for years where YEAR % 4 == 0 and anotherway for years where YEAR % 4 ~= 0
    leapmask = timestamps.apply(datetime.strftime,args=('%Y',)).astype(int) % 4 == 0
    hydrodoy = hydrodoy - 273
    hydrodoy.loc[leapmask] = hydrodoy.loc[leapmask] - 1 #Adjust for the leap year
    negleapmask = leapmask & (hydrodoy < 1)
    hydrodoy = hydrodoy.mask(hydrodoy < 1, hydrodoy+365) #Correct the days of the year prior to 1 October back to their order
    hydrodoy.loc[negleapmask] = hydrodoy.loc[negleapmask] + 1 #Adjust for the leap year
    return hydrodoy

def wateryear_from_timestamps(timestamps):
    """
    This function takes a pandas data Series object of timestamps and determines the hydrological year the date
    belongs to. Essentially, has to look at the year 92 days in the future.

    Needs error trapping or at least some type checking.
    """
    wateryears = timestamps + pd.Timedelta("92 day")
    wateryears = wateryears.apply(datetimepandas,args=('%Y',))
    wateryears = wateryears.astype(int)
    return wateryears

# ## Station Snow Statistics
#
# Interested in being able to correlate ENSO with timing of peak snow and amount of snow at the peak. Also interested in magnitude of peak melt rate and timing of the peak melt rate. These satistics will be part of a map-based view of the station data that will be colourized by the level of correlation or by the percent of peak snow associated with the
df['hydrodoy'] = hydrodoy_from_timestamp(df.index.to_series())
df['hydrological_year'] = wateryear_from_timestamps(df.index.to_series())


#Now have to find when that peak occurred...!
def count_coverage(series):
    return (~series.isna()).sum()

#pd.set_option('display.max_rows', 150)
#Find the number of years with more than 80% data coverage.
nyears_complete = (df.groupby(by="hydrological_year").apply(count_coverage)*100/365 > 80).sum(axis='rows')
#Get the peak snow each year:
peak_annual_snow = df.groupby(by="hydrological_year").apply(max)

#Now get stations with some chosen common period of record. Preferably this will be a subset of the stations with current
#and stations with more than x number of years.


#
# Need to bring in the monthly ENSO data. We'll probably use the Oceanic Nino Index for this.
# May want to alternatively or additionally bring in the monthly PNA and use some form of season-averaged PNA as
# a stratifire for snow. Should be more directly applicable to snow pack as it covaries with ENSO/is driven by it.
mnxonidata = get_wyear_extrema_oni(pd,np)
startrange = get_oni_startrange(mnxonidata)


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
currentyear = df[['hydrological_year']].max()
fillninoarea = 'rgba(255,110,95,0.3)'
fillninoline = 'rgb(255,110,95)'
fillninaarea = 'rgba(0,175,245,0.3)'
fillninaline = 'rgb(0,175,245)'
snowapp = Dash(__name__,
                  external_stylesheets = external_stylesheets,
                  title = 'ENSO Snow BC: exploring snow accumulation and El Nino/La Nina in British Columbia'
              )
server = snowapp.server
snowapp.layout = html.Div([
    #Call the function to produce the documentation using dcc.markdown
    header_text_md(dcc),
    dcc.Tabs(
        children=[
            dcc.Tab(
                label='ENSO Snow BC',
                children=[
                    html.Div(className='row', children=[
                        html.Div([
                        #Want to implement a checklist here that allows for the selection of one or more of three
                        #things
                        #
                        #1) Want to allow restriction to long records only
                        #2) Want to allow restriction to records with current year only
                        #3) Want an option to show only locations with data in an overlapping 30 years
                        #   normal period or restricted normal period. 1991 -- 2020 or 2000
                        #   to 2020 ideally and restrict the stats to those.
                        dcc.Checklist(
                            options=[
                                {'label': 'Require current year?', 'value': 'rcy'},
                                {'label': 'Require 20 or more years?', 'value': 'rtmy'},
                            #    {'label': 'Require current normal preiod', 'value': 'rcnp'},
                            ],
                            value=['rcy'],
                            #inline=True,
                            id='record-length-current-check',
                        )
                    ], className='four columns',),
                    html.Div([
                    html.P("Filter by La Niña/El Niño Strength:"),
                    dcc.RangeSlider(
                        min=-3,
                        max=3,
                        step=0.1,
                        #Range slider with custom marks.
                        marks={
                            -2.7: {'label': 'Extreme La Niña', 'style': {'color': fillninaline}},
                            -1.3: {'label': 'Mod. La Niña', 'style': {'color': fillninaline}},
                            -0.50: {'label': 'Neutral', 'style': {'color': 'rgb(80,80,80)'}},
                            0.50: {'label': 'Neutral', 'style': {'color': 'rgb(80,80,80)'}},
                            1.3: {'label': 'Mod. El Niño', 'style': {'color': fillninoline}},
                            2.7: {'label': 'Extreme El Niño', 'style': {'color': fillninoline}}
                        },
                        value=[startrange[0], startrange[1]],
                        updatemode='drag',
                        id='oni-range-slider'),
                    ], className='eight columns',),
                ]),
                html.Div(className='row', children=[
                    html.Div([
                        dcc.Graph(
                            id="snow-station-map",
                            #This is the initil point to draw data for. Clunky way of assigning it...
                            clickData={'points': [{'text': '3A25P Squamish River Upper<br>Elevation: 1360.0'}]},
                            #Get rid of the selection buttons in the map because they will confuse with
                            #The select on click action that's desired.
                            config={
                                'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']
                            }
                        ),
                    ], className='four columns',),
                    html.Div([
                        dcc.Graph(id="snow-station-graph",
                            config={
                                'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'autoScale2d'],
                                'modeBarButtonsToAdd': ['v1hovermode'],
                            }
                        ),
                    ], className='eight columns'),
                ]),
                ]
            ),
            dcc.Tab(
                label='Analysis',
                children=[
                    analysis_desc_md(dcc),
                ]
            ),
            dcc.Tab(
                label='Help',
                children=[
                    how_to_md(dcc),
                ]
            )
        ]
    ),
    footer_text_md(dcc),
])

@snowapp.callback(
    Output('snow-station-map', 'figure'),
    Input('record-length-current-check','value'),
)
def make_station_map(reccheck):
    '''
    Work with the record length checklist to filter the location data according to
    what is available in the master dataframe. The argument reccheck is the list
    of strings created as output by the checklist that indicates the logical
    filters. If present, then true, if absent, no filter.
    '''
    locdfuse = locdf
    if ('rcy' in reccheck):
        #Only keep stations with current year's data
        locdfuse = locdfuse.loc[(locdfuse['LCTN_ID'] + ' ' + locdfuse['LCTN_NM']).isin(pd.Series(stations_with_current_year)),:]
    if ('rtmy' in reccheck):
        #Only keep stations that have 30 or more years of complete records.
        locdfuse = locdfuse.loc[(locdfuse['LCTN_ID'] + ' ' + locdfuse['LCTN_NM']).isin(pd.Series(nyears_complete.index[nyears_complete >= 20])),:]

    return draw_station_map(go,locdfuse)

#Now make a callback that uses the values from the drop down and the slider selection to stratify the
#data and make the plot

@snowapp.callback(
    Output('snow-station-graph', 'figure'),
    Input('oni-range-slider', 'value'),
    Input('snow-station-map', 'clickData'),
)
def update_line_chart(onirange,clickData):
    '''
    Function to take the output from the slider and the station map callbacks
    and filter the master dataframe and the years according to the ONI magnitude
    Then calls a subfunction to create the actual map.
    '''
    maxdayidx = 321
    #Here's what the clickData look like:
    #{'points': [{
    #   'curveNumber': 0,
    #   'pointNumber': 123,
    #   'pointIndex': 123,
    #   'lon': -128.711028,
    #   'lat': 55.152028,
    #   'text': '4B18P Cedar-Kiteen<br>Elevation: 885.0',
    #   'bbox': {
    #        'x0': 76.35033446674115,
    #        'x1': 78.35033446674115,
    #        'y0': 1802.8100327553746,
    #        'y1': 1804.8100327553746
    #   }
    #}
    #]
    #}
    #
    stnname = clickData['points'][0]['text'].split('<br>')[0]
    subdf = pd.pivot_table(
                df[[stnname,'hydrological_year','hydrodoy']],
                index=["hydrodoy"],
                columns="hydrological_year",
                values=stnname
            )
    yearsuse = mnxonidata.index[(mnxonidata["ANOM"] > onirange[0]) &
        (mnxonidata["ANOM"] < onirange[1])].unique()
    if ((onirange[0] + onirange[1])/2 > 0):
        fillarea = fillninoarea
        fillline = fillninoline
    else:
        fillarea = fillninaarea
        fillline = fillninaline

    plottitle="Hydrologic Year SWE for \"{}\"<br>Oceanic Niño Index Range {} to {}".format(stnname,onirange[0],onirange[1])
    return snow_lineplot(
        go,
        pd,
        subdf,
        yearsuse,
        currentyear,
        maxdayidx,
        fillarea,
        fillline,
        plottitle=plottitle
    )

if __name__ == '__main__':
    snowapp.run(debug=False)
