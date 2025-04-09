import time
from snowdata import count_coverage

def snow_lineplot(go,pd,subdf,yearsuse,currentyear,fillarea,fillline,plottitle):
    '''
    This is the line plotting function stripped out of the snowapp to simplify that code somewhat.
    Has dependencies on pandas and plotly graph objcts, so these are brought in
    as function arguments

    subdf:
    yearsuse:
    currentyear:
    fillarea:
    filline:
    plottitle:
    '''
    maxdayidx = 321
    target_quantiles = [
        0.05,
        0.1587,
        0.25,
        0.5,
        0.75,
        0.8413,
        0.95
    ]
#    quant_colors = [
#        'rgba(244,0,0,0.8)', 
#        'rgba(252,78,42,0.8)', 
#        'rgba(244,244,0,0.8)',
#       'rgba(100,100,100,0.8)',
#       'rgba(0,244,21,0.8)',
#        'rgba(20,143,54,0.8)',
#        'rgba(0,5,230,0.8)',
#    ]
    quant_colors = [
        'rgba(244,0,0,0.8)', 
        'rgba(252,78,42,0.8)', 
        'rgba(244,244,0,0.8)',
        'rgba(100,100,100,0.8)',
        'rgba(0,244,21,0.8)',
        'rgba(20,143,54,0.8)',
        'rgba(0,5,230,0.8)',
    ]
    quant_dashstyle = [
        '3, 4',
        '10,3',
        None,
        None,
        None,
        '10, 3',
        '3, 4',
    ]
    if any(currentyear.isin(subdf.columns)):
        station_is_active = True
        statoffset=1
    else:
        station_is_active = False
        statoffset=0

    nyears = len(subdf.columns)
    
    completestat = (1-(subdf.iloc[0:maxdayidx,:].isna().sum(axis='rows'))/maxdayidx)>0.95
    '''
    we have to calculate the quantiles on all years except the current
    and incomplete years. Partial years make weird quantiles where data
    drops in and out.
    '''
    quantiles = subdf.loc[:,completestat].quantile(target_quantiles,axis=1,interpolation='midpoint').transpose()
    subdf = pd.concat([subdf,quantiles],axis=1,copy=False,)


    yearsavail = subdf.columns[subdf.columns.isin(yearsuse)]
    filtereddf = subdf.loc[:,yearsavail]
    nyearssub = len(filtereddf.columns)
    completestat = (1-(filtereddf.iloc[0:maxdayidx,:].isna().sum(axis='rows'))/maxdayidx)>0.95
    quantiles = filtereddf.loc[:,completestat].quantile(target_quantiles,axis=1,interpolation='midpoint').transpose()
    filtereddf = pd.concat([filtereddf,quantiles],axis=1,copy=False,)
    
    fig = go.Figure()
    #These next four add_trace/go.Scatter calls/objects build the median and range lines/area plots.
    #Range for the full dataset.
    #Only plot ranges if more than 5 years of record
    if nyears >= 5:
        fig.add_trace(go.Scatter(
            x=pd.concat([subdf.index.to_series()[0:maxdayidx],subdf.index.to_series()[maxdayidx:0:-1]]),
            y=pd.concat([subdf[0.1587].iloc[0:maxdayidx],subdf[0.8413].iloc[maxdayidx:0:-1]]),
            fill='toself',
            fillcolor='rgba(100,100,100,0.2)',
            line_color='rgba(255,255,255,0)',
            legendgroup='fullrecord',
            showlegend=True,
            name="1" + u"\u03C3"+" Range"
        ))
    #Median for the full dataset
    fig.add_trace(go.Scatter(
        x=subdf.index.to_series()[0:maxdayidx],
        y=subdf[0.5].iloc[0:maxdayidx],
        #y=subdf.iloc[:,0:(nyears-statoffset)].median(axis=1)[0:maxdayidx],
        line_color='rgb(100,100,100)',
        legendgroup='fullrecord',
        name='Median'
    ))
    if nyearssub >= 5:
        #Range for the ENSO subset of the data.
        fig.add_trace(go.Scatter(
            x=pd.concat([subdf.index.to_series()[0:maxdayidx],subdf.index.to_series()[maxdayidx:0:-1]]),
            y=pd.concat([filtereddf[0.1587].iloc[0:maxdayidx],filtereddf[0.8413].iloc[maxdayidx:0:-1]]),
            fill='toself',
            fillcolor=fillarea,
            line_color='rgba(255,255,255,0)',
            legendgroup='onisub',
            showlegend=True,
            name="1" + u"\u03C3"+" Selected Range"
        ))
    #Median for the ENSO subset of the data.
    fig.add_trace(go.Scatter(
        x=subdf.index.to_series()[0:maxdayidx],
        y=filtereddf[0.5].iloc[0:maxdayidx],
        #y=filtereddf.iloc[:,0:(nyearssub-statoffset)].median(axis=1)[0:maxdayidx],
        line_color=fillline,
        legendgroup='onisub',
        name='Selected Median'
    ))
    #lets iterate through the years and plot the individual years with only the legend entry
    #Strategy to get the plot to show only years of interest.
    # 1) by default only show a shaded range between max and min with a line for median snow
    # 2) When the data are stratified by ENSO, add to the figure with attribute visible='legendonly'
    #    Like this:

    #Okay, need to always plot the current year and not plot the current year a second time if
    #The current year is included in the filtered data frame.
    if any((currentyear.isin(yearsavail))):
        #Deindex this by one so that the current year isn't plotted twice when the ENSO selection includes the
        #ENSO value of the current year.
        yearsavail = yearsavail[0:(len(yearsavail)-1)]

    #Put the 0.05, 0.25, 0.75, 0.95 quantiles on the plot
    for i in [0,2,4,6]:
        fig.add_trace(
            go.Scatter(
                x=subdf.index.to_series()[0:maxdayidx],
                y=subdf[target_quantiles[i]].iloc[0:maxdayidx],
                visible='legendonly',
                name='{percentile:0.1f}%-ile'.format(percentile = 100*target_quantiles[i]),
                legend='legend3',
                line=dict(color='rgba(75,75,75,20)', width=1.25, dash=quant_dashstyle[i]),
                #line=dict(color=quant_colors[i], width=3, dash=quant_dashstyle[i]),
            )
        )
    for ayear in yearsavail:
        fig.add_trace(
            go.Scatter(
                x=filtereddf.index.to_series()[0:maxdayidx],
                y=filtereddf[ayear].iloc[0:maxdayidx],
                visible='legendonly',
                name=str(int(ayear)),
                legend='legend2',
            )
        )

    #Finally, plot the current year on the chart if the station is active.
    if station_is_active:
        fig.add_trace(
            go.Scatter(
                x=subdf.index.to_series()[0:maxdayidx],
                y=subdf[currentyear.iloc[0]].iloc[0:maxdayidx],
                name='{}'.format(currentyear.iloc[0]),
                line_color='rgb(0,0,0)',
                legend='legend2',
            )
        )

    fig.update_layout(
        title = dict(text = plottitle,
                     font = dict(size=18)),
        #xaxis_title = dict(text="Date", font=dict(size=18)),
        xaxis = dict(
            type='category',
            tickfont=dict(size=14),
            tickmode = 'array',
            tickvals = ['10-01', '11-01', '12-01', '01-01', '02-01', '03-01', '04-01', '05-01', '06-01', '07-01', '08-01'],
            ticktext = ['1 Oct', '1 Nov', '1 Dec', '1 Jan', '1 Feb', '1 Mar', '1 Apr', '1 May', '1 Jun', '1 Jul', '1 Aug']
        ),
        yaxis_title=dict(text="Snow Water Equivalent (mm)", font=dict(size=18)),
        yaxis = dict(
            tickfont=dict(size=16)
        ),
        legend=dict(
            orientation="h",
            x=0.0,
            y=1
        ),
        legend2=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="left",
            x=0.0
        ),
        legend3=dict(
            orientation="v",
            #yanchor="top",
            y=1,
            #xanchor="left",
            x=0.85,
        )
    )
    return fig
