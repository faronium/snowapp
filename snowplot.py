


def snow_lineplot(go,pd,subdf,yearsuse,currentyear,maxdayidx,fillarea,fillline,plottitle):
    '''
    This is the line plotting function stripped out of the snowapp to simplify that code somewhat.
    Has dependencies on pandas and plotly graph objcts, so these are brought in
    as function arguments

    subdf:
    yearsuse:
    currentyear:
    maxdayidx:
    fillarea:
    filline:
    plottitle:
    '''

    if any(currentyear.isin(subdf.columns)):
        station_is_active = True
        statoffset=1
    else:
        station_is_active = False
        statoffset=0

    nyears = (len(subdf.columns))
    #Can probably replace the two-line calculation of min with a more complex where or mask statement
    subdf['min'] = subdf.iloc[:,0:(nyears-statoffset)].median(axis=1) - subdf.iloc[:,0:(nyears-statoffset)].std(axis=1)
    subdf.loc[(subdf['min'] < 0),'min'] = 0
    #Need to set the min and max range values to zero where they drop to negative snow amounts


    yearsavail = subdf.columns[subdf.columns.isin(yearsuse)]
    filtereddf = subdf.loc[:,yearsavail]
    nyearssub = len(filtereddf.columns)
    #Can probably replace the two-line calculation of min with a more complex where or mask statement
    filtereddf['min'] = filtereddf.iloc[:,0:(nyearssub-statoffset)].median(axis=1) - filtereddf.iloc[:,0:(nyearssub-statoffset)].std(axis=1)
    filtereddf.loc[(filtereddf['min'] < 0 ),'min'] = 0
    #Need to set the min and max range values to zero where they drop to negative snow amounts
    fig = go.Figure()
    #These next four add_trace/go.Scatter calls/objects build the median and range lines/area plots.
    #Range for the full dataset.
    #Only plot ranges if more than 5 years of record
    if nyears >= 5:
        fig.add_trace(go.Scatter(
            x=pd.concat([subdf.index.to_series()[0:maxdayidx],subdf.index.to_series()[maxdayidx:0:-1]]),
            y=pd.concat([subdf.loc[0:maxdayidx,'min'],(subdf.iloc[:,0:(nyears-statoffset)].median(axis=1) + subdf.iloc[:,0:(nyears-statoffset)].std(axis=1))[maxdayidx:0:-1]]),
            fill='toself',
            fillcolor='rgba(100,100,100,0.2)',
            line_color='rgba(255,255,255,0)',
            legendgroup='fullrecord',
            showlegend=True,
            name='Range'
        ))
    #Median for the full dataset
    fig.add_trace(go.Scatter(
        x=subdf.index[0:maxdayidx],
        y=subdf.iloc[:,0:(nyears-statoffset)].median(axis=1)[0:maxdayidx],
        line_color='rgb(100,100,100)',
        legendgroup='fullrecord',
        name='Median'
    ))
    if nyearssub >= 5:
        #Range for the ENSO subset of the data.
        fig.add_trace(go.Scatter(
            x=pd.concat([subdf.index.to_series()[0:maxdayidx],subdf.index.to_series()[maxdayidx:0:-1]]),
            y=pd.concat([filtereddf.loc[0:maxdayidx,'min'],(filtereddf.iloc[:,0:(nyearssub-statoffset)].median(axis=1) + filtereddf.iloc[:,0:(nyearssub-statoffset)].std(axis=1))[maxdayidx:0:-1]]),
            fill='toself',
            fillcolor=fillarea,
            line_color='rgba(255,255,255,0)',
            legendgroup='onisub',
            showlegend=True,
            name='Selected Range'
        ))
    #Median for the ENSO subset of the data.
    fig.add_trace(go.Scatter(
        x=subdf.index[0:maxdayidx],
        y=filtereddf.iloc[:,0:(nyearssub-statoffset)].median(axis=1)[0:maxdayidx],
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

    for ayear in yearsavail:
        fig.add_trace(
            go.Scatter(
                x=filtereddf.index[0:maxdayidx],
                y=filtereddf.loc[0:maxdayidx,ayear],
                visible='legendonly',
                name=ayear,
                legend='legend2',
            )
        )
    #Plot the current year on the chart if the station is active.
    if station_is_active:
        fig.add_trace(
            go.Scatter(
                x=subdf.index[0:maxdayidx],
                y=subdf.loc[0:maxdayidx,currentyear[0]],
                name='{}'.format(currentyear[0]),
                line_color='rgb(0,0,0)',
                legend='legend2',
            )
        )

    fig.update_layout(
        title = dict(text = plottitle,
                     font = dict(size=18)),
        #xaxis_title = dict(text="Date", font=dict(size=18)),
        xaxis = dict(
            tickfont=dict(size=14),
            tickmode = 'array',
            tickvals = [1, 32, 62, 93, 124, 152, 183, 213, 244, 274, 305],
            ticktext = ['1 Oct.', '1 Nov.', '1 Dec.', '1 Jan.', '1 Feb.', '1 Mar.', '1 Apr.', '1 May', '1 Jun.', '1 Jul.', '1 Aug.']
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
        )
    )
    return fig
