#!/usr/bin/env python
# coding: utf-8

# # Snow Data
#
# Tool to import archived snow data and manipulate it using python pandas. Eventually
# to plot with plotlinkedinly/dash app of some kind.
#



import pandas as pd
import numpy as np
from dash import Dash, html, dcc, Input, Output, callback
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from datetime import datetime
import time
from snowdata import get_wyear_extrema_oni, get_oni_startrange, load_munge_snow_data, count_coverage, get_median
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

pd.set_option('display.max_rows', 30)
df, stations_with_current_year = load_munge_snow_data()

#lets figure out how to make quantiles for each station/day and 
#compute the percentile amount relative to median for all stations.
#The quantiles will need to be passed into the plotting function
#To be shown.

#We only need the median outside of the line plotting function, 
#so we can save the full quantile calculation for there. 

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

#Add on the month-day column for better plotting
df['month-day'] = df.index.strftime('%m-%d')
#Drop all leap years
df = df.loc[(~(df['month-day']=='02-29')),:]

#pd.set_option('display.max_rows', 150)
#Find the number of years with more than 80% data coverage.
nyears_complete = (df.groupby(by="hydrological_year").apply(count_coverage,include_groups=False)*100/365 > 80).sum(axis='rows')
nyears_complete = nyears_complete[:-2]
#Get the peak snow each year:
peak_annual_snow = df.iloc[:,:-1].groupby(by="hydrological_year").max()
peak_annual_snow = peak_annual_snow.iloc[:,:-1]
historical_median_snow = df.iloc[:,:-2].groupby(by="hydrodoy").mean()

#peak_annual_snow
dftest = df.copy()
#keep the index
dates = df.index
dftest = dftest.set_index(['hydrodoy'],append=True).iloc[:,:-2]
historical_median_snow = dftest.rolling(window=5,center=True).mean().groupby(level=1).mean()

#dftest = dftest.iloc[:,:-3]
dftest.sort_index(level=['hydrodoy'])
#pd.set_option('display.max_rows', None)
#dftest.loc[(slice(None),1),:]
pd.set_option('display.max_rows', 30)
snow_pct_median = 100*(dftest/historical_median_snow)
snow_pct_median.replace([np.inf], 399, inplace=True)
snow_pct_median[snow_pct_median > 399] = 400
snow_pct_now = snow_pct_median.iloc[-1:,].reset_index(drop=True).T #=range(126) #= snow_pct_median.iloc[-1:,].T


#check to see if we have a 1:1 match of the current snow percentage with the locations dataframe
if (snow_pct_now.index == locdf['LCTN_ID'] + ' ' + locdf['LCTN_NM']).all():
    locdf['pct_snow'] = snow_pct_now.iloc[:,0].values
else:
    None

mnxonidata = get_wyear_extrema_oni()
startrange = get_oni_startrange(mnxonidata)


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
currentyear = df[['hydrological_year']].max()
fillninoarea = 'rgba(255,110,95,0.3)'
fillninoline = 'rgb(255,110,95)'
fillninaarea = 'rgba(0,175,245,0.3)'
fillninaline = 'rgb(0,175,245)'

snowapp = Dash(__name__,
                  external_stylesheets = [dbc.themes.SANDSTONE],
                  title = 'ENSO Snow BC: exploring snow accumulation and El Nino/La Nina in British Columbia'
              )
server = snowapp.server

reclengthselect = html.Div(
    [
        #Want to implement a checklist here that allows for the selection of one or more of three
        #things
        #
        #1) Want to allow restriction to long records only
        #2) Want to allow restriction to records with current year only
        dcc.Checklist(
            options=[
                {'label': 'Active stations?', 'value': 'rcy'},
                {'label': '20+ years of record?', 'value': 'rtmy'},
            ],
            value=['rcy'],
            id='record-length-current-check',
        )
    ],
)


anomselect = html.Div(
    [
        #Want to implement a check whether to show the maps with anomalies or not.
        dcc.Checklist(
            options=[
                {'label': 'Plot station anomalies?', 'value': 'anomstat'},
            ],
            value=[],
            id='show-anoms-stat',
        ),
    ],
)

slider = html.Div(
    [
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
    ],
)

snowmap = html.Div(
    [
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
    ],
)

snowgraph = html.Div(
    [
        dcc.Graph(id="snow-station-graph",
            config={
                'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'autoScale2d'],
                'modeBarButtonsToAdd': ['v1hovermode'],
            }
        ),
    ],
)

snowapp.layout = html.Div([
    #Call the function to produce the documentation using dcc.markdown
    header_text_md(dcc),
    dbc.Card([dbc.Tabs(
        children=[
            dbc.Tab([
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.Row([
                                dbc.Col([reclengthselect,],),
                                dbc.Col([anomselect,],),
                            ]),
                            snowmap,
                        ],
                        className="shadow",
                        )
                    ],
                    width=4,
                    ),
                    dbc.Col([
                        dbc.Card([
                            slider,
                            snowgraph
                        ],
                        className="shadow",
                        )
                    ],
                    width=8,
                   )
                ]
                ),
            ],
            label='ENSO Snow BC',
            ),
            dbc.Tab(
                label='Analysis',
                children=[
                    analysis_desc_md(dcc),
                ]
            ),
            dbc.Tab(
                label='Help',
                children=[
                    how_to_md(dcc),
                ]
            )
        ]
    )]),
    footer_text_md(dcc),
])

@snowapp.callback(
    Output('snow-station-map', 'figure'),
    Input('record-length-current-check','value'),
    Input('show-anoms-stat','value'),
)
def make_station_map(reccheck,anomstat):
    '''
    Work with the record length checklist to filter the location data according to
    what is available in the master dataframe. The argument reccheck is the list
    of strings created as output by the checklist that indicates the logical
    filters. If present, then true, if absent, no filter.
    '''
    if len(anomstat) == 0:
        #Plot single color symbols on the station map
        anomstat=False
    else:
        #Plot colors according to the current daily station anomaly
        anomstat=True
    locdfuse = locdf
    if ('rcy' in reccheck):
        #Only keep stations with current year's data
        locdfuse = locdfuse.loc[(locdfuse['LCTN_ID'] + ' ' + locdfuse['LCTN_NM']).isin(pd.Series(stations_with_current_year)),:]
    if ('rtmy' in reccheck):
        #Only keep stations that have 30 or more years of complete records.
        locdfuse = locdfuse.loc[(locdfuse['LCTN_ID'] + ' ' + locdfuse['LCTN_NM']).isin(pd.Series(nyears_complete.index[nyears_complete >= 20])),:]

    return draw_station_map(go,locdfuse,anomstat)

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
    stnname = clickData['points'][0]['text'].split('<br>')[0]
    subdf = pd.pivot_table(
                df[[stnname,'hydrological_year','month-day']],
                index=['month-day'],
                columns="hydrological_year",
                values=stnname
            )
    #The pivot re-orders the intex. 
    #need to stack the bottom onto the top to make a hydrological year
    subdf = pd.concat([subdf.iloc[-92:,:],subdf.iloc[0:(366-92):,]],axis=0)
    yearsuse = mnxonidata.index[(mnxonidata["ANOM"] > onirange[0]) &
        (mnxonidata["ANOM"] < onirange[1])].unique()
    if ((onirange[0] + onirange[1])/2 > 0):
        fillarea = fillninoarea
        fillline = fillninoline
    else:
        fillarea = fillninaarea
        fillline = fillninaline

    plottitle="Hydrologic Year SWE for \"{}\" Oceanic Niño Index Range {} to {}".format(stnname,onirange[0],onirange[1])
    return snow_lineplot(
        go,
        pd,
        subdf,
        yearsuse,
        currentyear,
        fillarea,
        fillline,
        plottitle=plottitle
    )

if __name__ == '__main__':
    snowapp.run(debug=False)




