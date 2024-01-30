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

#Snow data URL: https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/
#ONI data URL: https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
#PNA data URL: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.pna.monthly.b5001.current.ascii
#NAO data URL: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.nao.monthly.b5001.current.ascii
#All teleconnections in one! ftp://ftp.cpc.ncep.noaa.gov/wd52dg/data/indices/tele_index.nh

df = pd.read_csv('./snow/SW_DailyArchive.csv',index_col=[0],parse_dates=[0]) #Here the [0] tells fxn to parse first column
#df = pd.read_csv('https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/SW_DailyArchive.csv',index_col=[0],parse_dates=[0]) #Here the [0] tells fxn to parse first column

# In[43]:


#dffresh = pd.read_csv('./snow/SWDaily.csv',index_col=[0],parse_dates=[0])
dffresh = pd.read_csv('https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/SWDaily.csv',index_col=[0],parse_dates=[0])
df = pd.concat([df,dffresh],axis=0)


# ## Munging data to consistent timestamps and getting some useful indexes

# 
# Looks like there are stations that have data at a non-standard time of 16:00. Six stations that have data on the even hour at some point in their record. These are '1A02P McBride Upper', '1B02P Tahtsa Lake', '1B08P Mt. Pondosy', '2F18P Brenda Mine', '3A25P Squamish River Upper', '3A28P Tetrahedron'. In all of these stations, the hourly data is in addition to the data reported at 16:00. So, can safely drop all of the excess data without worry. 
# 
# 

# In[4]:


#Deal with the non-daily observations. Most are on the 16:00, some are on the 00:00 and others are on the even hour.
#plt.close("all")
#Set the rows with hours != 16:00 to NaN for stations '1A02P McBride Upper', '1B02P Tahtsa Lake', '1B08P Mt. Pondosy', '2F18P Brenda Mine', 
#         '3A25P Squamish River Upper', '3A28P Tetrahedron']
df.loc[df.index.strftime('%H').isin(['00','01','02','03','04','05','06','07','08','09','10','11',
        '12','13','14','15','17','18','19','20','21','22','23']),
        ['1A02P McBride Upper', '1B02P Tahtsa Lake', '1B08P Mt. Pondosy', '2F18P Brenda Mine', 
         '3A25P Squamish River Upper', '3A28P Tetrahedron']] = np.nan


# 
# Additionally, the stations '4D16P Forrest Kerr Mid Elevation Snow', '4D17P Forrest Kerr High Elevation Snow' have data on the 00:00. These also appear not to have data on the 16:00. So, perhaps we can simply move those timestamps by the 16 hours to make them 

# In[5]:


dfsub = df[['4D16P Forrest Kerr Mid Elevation Snow','4D17P Forrest Kerr High Elevation Snow']]
dfsub = dfsub.dropna(axis=0,how='all')
dfsub.index += pd.Timedelta("16 hours")


# 
# Now simply merge the two data frames into a master data frame that only has the data we want. 
# 

# In[6]:


df.loc[df.index.strftime('%H') == '22',~df.columns.isin(['4D16P Forrest Kerr Mid Elevation Snow','4D17P Forrest Kerr High Elevation Snow'])] = np.nan
df = df.loc[:,~df.columns.isin(['4D16P Forrest Kerr Mid Elevation Snow','4D17P Forrest Kerr High Elevation Snow'])].join(dfsub)
df = df.dropna(axis=0,how='all')
df = df.loc[:,df.columns.sort_values().unique()]


# In[7]:


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

df['hydrodoy'] = hydrodoy_from_timestamp(df.index.to_series())
df['hydrological_year'] = wateryear_from_timestamps(df.index.to_series())


# In[88]:





# 
# Make a column formatted so that gives the hydrological year. Essentially the time index, forward by 3 months,
# then reformatted to %Y using strftime.
# 

# ## Station Snow Statistics
# 
# Interested in being able to correlate ENSO with timing of peak snow and amount of snow at the peak. Also interested in magnitude of peak melt rate and timing of the peak melt rate. These satistics will be part of a map-based view of the station data that will be colourized by the level of correlation or by the percent of peak snow associated with the 

# 
# Need to bring in the monthly ENSO data. We'll probably use the Oceanic Nino Index for this.
# May want to alternatively or additionally bring in the monthly PNA and use some form of season-averaged PNA as
# a stratifire for snow. Should be more directly applicable to snow pack as it covaries with ENSO/is driven by it.

# In[13]:


#Import oceanic Nino index and massage into a form that allows selection by ENSO strength

onidata = pd.read_fwf('./snow/oni.ascii.txt')
oniseaslist = list(['OND','NDJ','DJF','JFM','FMA','MAM'])
onidata = onidata[onidata['SEAS'].isin(oniseaslist)]
#onidata = pd.read_fwf('https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt')
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
if mnxonidata.loc[mnxonidata.index[(len(mnxonidata)-1)],"ANOM"] > 0.5:
    startrange = [0.5,3]
elif mnxonidata.loc[mnxonidata.index[(len(mnxonidata)-1)],"ANOM"] < 0.5:
    startrange = [-3,-0.5]
else:
    startrange = [-0.5,0.5]



# ## Build the app
# 
# Okay, the daily snow water equivalent data are munged into a form that is relatively clean and useful and we have the tools to stratify the data by year, hydrological day of the year and station. Time to build the app. We want a simple layout that has a snow station selector at the top along with an ENSO strength slider with La Nina max on the left and El Nino max on the right. Perhaps most ideal would be slider with two tabs that alows the picking of a max and a min ONI value. Will have to think about this. 

# In[50]:


fillninoarea = 'rgba(255,110,95,0.2)'
fillninoline = 'rgb(255,110,95)'
fillninaarea = 'rgba(0,175,245,0.2)'
fillninaline = 'rgb(0,175,245)'
maxdayidx = 321
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
snowapp = Dash(__name__, external_stylesheets=external_stylesheets)
server = snowapp.server
snowapp.layout = html.Div([
    dcc.Markdown(
        '''
        ### Multi-year Snow Water Equivalent Stratified by ENSO Strength
        
        This app allows the exploration of the relationship between snow accumulation and the 
        El Nino Southern Oscillation (ENSO) in the province of British Columbia. There is a strong
        relationship between BC's weather in winter and spring and the state of ENSO.
        
        This app utilizes snow water equivalent data collected by the BC Ministry of Environment 
        and Climate Change Strategy and its partners BC Hydro, and Rio Tinto. Data are collected
        using instruments called snow pillows which weigh the overlying snow and that weight is 
        converted to the water equivalent snow amount of the overlying snowpack.
        
        ___
        '''
    ),
    dcc.Dropdown(
        df.columns[0:124],
        '2F05P Mission Creek',
        id='snow-station-name',
        multi=False  #multi=True
    ),
    dcc.Graph(id="snow-station-graph"),
    html.H5("Filter by La Niña/El Niño Strength:"),
    dcc.RangeSlider(min=-3,
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
                    id='oni-range-slider')
])

#Now make a callback that uses the values from the drop down and the slider selection to stratify the 
#data and make the plot

@snowapp.callback(
    Output("snow-station-graph", "figure"), 
    Input("oni-range-slider", "value"),
    Input("snow-station-name","value"))
def update_line_chart(onirange,stationname):
    #subdf = df[[stationname,'hydrological_year','hydrodoy']]
    subdf = pd.pivot_table(df[[stationname,'hydrological_year','hydrodoy']],index=["hydrodoy"],columns="hydrological_year",values=stationname)
    #Can probably replace the two-line calculation of min with a more complex where or mask statement
    subdf['min'] = subdf.median(axis=1) - subdf.std(axis=1)
    subdf.loc[(subdf['min'] < 0),'min'] = 0
    #Need to set the min and max range values to zero where they drop to negative snow amounts
    if ((onirange[0] + onirange[1])/2 > 0):
        fillarea = fillninoarea
        fillline = fillninoline
    else:
        fillarea = fillninaarea
        fillline = fillninaline
    
    yearsuse = mnxonidata.index[(mnxonidata["ANOM"] > onirange[0]) & 
        (mnxonidata["ANOM"] < onirange[1])].unique()
    filtereddf = subdf.loc[:,subdf.columns.isin(yearsuse)]
    #Can probably replace the two-line calculation of min with a more complex where or mask statement
    filtereddf['min'] = filtereddf.median(axis=1) - filtereddf.std(axis=1)
    filtereddf.loc[(filtereddf['min'] < 0 ),'min'] = 0
    #Need to set the min and max range values to zero where they drop to negative snow amounts
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pd.concat([subdf.index.to_series()[0:maxdayidx],subdf.index.to_series()[maxdayidx:0:-1]]),
        y=pd.concat([subdf.loc[0:maxdayidx,'min'],(subdf.median(axis=1) + subdf.std(axis=1))[maxdayidx:0:-1]]),
        fill='toself',
        fillcolor='rgba(100,100,100,0.2)',
        line_color='rgba(255,255,255,0)',
        legendgroup='fullrecord',
        showlegend=True,
        name='Range'
    ))
    fig.add_trace(go.Scatter(
        x=subdf.index[0:maxdayidx], 
        y=subdf.median(axis=1)[0:maxdayidx],
        line_color='rgb(100,100,100)',
        legendgroup='fullrecord',
        name='Median'
    ))
    fig.add_trace(go.Scatter(
        x=pd.concat([subdf.index.to_series()[0:maxdayidx],subdf.index.to_series()[maxdayidx:0:-1]]),
        y=pd.concat([filtereddf.loc[0:maxdayidx,'min'],(filtereddf.median(axis=1) + filtereddf.std(axis=1))[maxdayidx:0:-1]]),
        fill='toself',
        fillcolor=fillarea,
        line_color='rgba(255,255,255,0)',
        legendgroup='onisub',
        showlegend=True,
        name='Selected Range'
    ))
    fig.add_trace(go.Scatter(
        x=subdf.index[0:maxdayidx],
        y=filtereddf.median(axis=1)[0:maxdayidx],
        line_color=fillline,
        legendgroup='onisub',
        name='Selected Median'
    ))
    #lets iterate through the years and plot the individual years with only the legend entry
    #Strategy to get the plot to show only years of interest. 
    # 1) by default only show a shaded range between max and min with a line for median snow
    # 2) When the data are stratified by ENSO, add to the figure with attribute visible='legendonly'
    #    Like this: 
    for ayear in filtereddf.columns[0:len(filtereddf.columns)-2]:
        fig.add_trace(
            go.Scatter(
                x=filtereddf.index[0:maxdayidx],
                y=filtereddf.loc[0:maxdayidx,ayear],
                visible='legendonly',
                name=ayear,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=filtereddf.index[0:maxdayidx],
            y=filtereddf.loc[0:maxdayidx,filtereddf.columns[len(filtereddf.columns)-2]],
            name=filtereddf.columns[len(filtereddf.columns)-2],
            line_color='rgb(0,0,0)'
        )
    )
    fig.update_layout(
        title = dict(text="Hydrologic Year SWE for \"{}\"<br>Oceanic Niño Index Range {} to {}".format(stationname,onirange[0],onirange[1]),
                     font=dict(size=22)),
        xaxis_title = dict(text="Date", font=dict(size=22)),
        xaxis = dict(
            tickfont=dict(size=14),
            tickmode = 'array',
            tickvals = [1, 32, 62, 93, 124, 152, 183, 213, 244, 274, 305],
            ticktext = ['1 Oct.', '1 Nov.', '1 Dec.', '1 Jan.', '1 Feb.', '1 Mar.', '1 Apr.', '1 May', '1 Jun.', '1 Jul.', '1 Aug.']
        ),
        yaxis_title=dict(text="Snow Water Equivalent (mm)", font=dict(size=22)),
        yaxis = dict(
            tickfont=dict(size=14)
        )
    )


    return fig

if __name__ == '__main__':
    snowapp.run(debug=False)




