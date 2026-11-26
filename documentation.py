
def header_text_md(dcc):
    return dcc.Markdown(
        '''
        #### Multi-year Snow Water Equivalent Stratified by ENSO Strength
        There is a strong relationship between BC's weather in winter and spring and the state
        of the El Niño Southern Oscillation (ENSO) and this relationship translates to variability
        in the province's snowpack from year to year. This app allows the exploration of that
        relationship between snow accumulation and ENSO in the province of British Columbia.
        '''
        )

def analysis_desc_md(dcc):
    return dcc.Markdown(
        '''
        #### Data sources
        Snow water equivalent stations are maintained and operated by the [BC Ministry of Environment
        and Climate Change Strategy](https://www2.gov.bc.ca/gov/content/environment/air-land-water/water/water-science-data/water-data-tools/snow-survey-data)
        and its partners [BC Hydro](https://bchydro.com), [Rio Tinto](https://www.riotinto.com), and
        [Metro Vancouver](https://metrovancouver.org/). Data are collected using instruments called
        snow pillows which weigh the overlying snow and that weight is converted to the water
        equivalent content of the snowpack. Data are daily and comprise a daily archive
        through the previous water year and the continuously
        updated daily data for the most recent water year. The current-year snow data may have
        quality artifacts because the data have not been quality controlled. The Relative Oceanic Niño Index (RONI)
        is produced by the US National Oceanic and Atmospheric Administration's
        [Climate Prediction Center](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/),
        which adopted it as its official ENSO index in February 2026, replacing the Oceanic Niño Index (ONI).
        The index is based on sea surface temperature anomalies in the Niño 3.4 region of the tropical Pacific
        Ocean measured relative to the average across the tropics, which removes the influence of the long-term
        warming of tropical oceans.

        #### Analysis
        ###### Complete Seasons
        Medians and ranges are calculated only from *complete* seasons: past water years with data on at least
        95% of the days from 1 October to 16 August. The current season is never included. The legend on the
        graph and the station details on the map give the number of complete seasons and the years they span,
        which differ from station to station.
        ###### Snow Ranges
        The primary elements of the plot are the median snow water equivalent for each day of the water year
        and a range about that median. The range runs from the 15.87th to the 84.13th percentile of the data for
        that day, which covers the same share of the data as one standard deviation either side of the mean would
        for normally distributed data, but is taken directly from the data. Ranges are only shown when at least
        five complete seasons are available.
        A median and range are shown for each of the full record (in grey) and for the seasons selected by
        ENSO strength, coloured red for selections that are ENSO positive (El Niño) overall and
        blue for selections that are ENSO negative (La Niña). For example, if the RONI range is -0.5 to 2, the
        midpoint of the range is 0.75 and thus the plot of the subset will be red in color.
        ###### Map Colours
        With *Plot station anomalies?* ticked, each station is coloured by its most recent snow water equivalent
        (from the last three days of data) as a percentage of its median for that date, the same median as the
        grey line on the graph. Red is below the median and blue is above; the colours stop changing below 25%
        and above 175%. Stations are grey when they have not reported in the last three days, have no complete
        seasons to compare with, or normally have less than 10 mm of snow on that date (early and late in the
        season), when a percentage would be misleading. A colour key appears in the upper right of the map, and
        hovering over a station shows the values behind its colour.
        ###### The Relative Oceanic Niño Index
        The Relative Oceanic Niño Index for a given year is taken as the extrema for the winter season of interest.
        The underlying RONI data are over three-month periods and incorporate the seasons OND through MAM.
        Rules for the hydrological year are applied. So, for example, if the extrema of the RONI falls in
        either the OND or NDJ seasons of the year 2005, the ascribed year will be 2006. The slider element
        of the app is labelled with subjective ENSO strengths. These are mapped to RONI as follows:

        * -0.5 to 0.5 is ENSO neutral
        * -1.3 or 1.3 are mapped as moderate events
        * -2.7 or 2.7 are mapped as extreme events.

        RONI is resolved and may be selected at 0.1 degree increments. When the app opens, the slider is set
        to the ENSO phase of the most recent three-month RONI value.
        ###### Individual Snow Seasons
        The data from the individual years are presented as-is. As described above, the current year's data
        is likely to have spurious values that have not been corrected by quality control software.
        '''
    )

def how_to_md(dcc):
    '''
    This function contains the documentation for the app that appears in the webpage. It is formatted as
    markdown. Isolated this away from the rest of the app to clean up the code and keep this monster
    block from interfering with the readability of the already large application.

    Here dcc is the Dash Core Components from the initial import.
    '''
    return dcc.Markdown(
        '''
        #### How-to
        The primary component of this webpage is a graph that depicts the evolution of accumulated
        snow amount over the water year that runs from 1 October through 30 September in the
        subsequent year. User controls are:

        * **checkboxes** in the controls panel below the map to choose which stations are shown and how they are coloured;
        * a **slider** in the controls panel that allows for the selection of a range of values of the ENSO strength;
        * a **map** that shows the location of snow-pillow sites in BC;
        * a **graph** that plots the snow water equivalent for the hydrological year.

        The line at the bottom of the controls panel shows how recent the snow and RONI data are. The app checks
        its sources for new data every few hours.

        ###### The Checkboxes
        The first two checkboxes subset the stations shown on the map. *Active stations only?* shows stations
        that have data for the current water year. *Require 20 complete seasons?* shows only stations with
        at least 20 complete seasons (see the Analysis tab). These longer, more complete records are recommended
        for investigating the ENSO/snow relationship for a given station. Both are selected by default.
        *Plot station anomalies?* colours each station by its current snow water equivalent as a percentage
        of its median for the date, as described on the Analysis tab.

        ###### The ENSO Slider
        The slider allows for the selection of a range of values of the ENSO strength as
        determined by the Relative Oceanic Niño Index (RONI). Click and drag the handles or click on the slider
        bar and the range will adjust to your input. The **graph** title will respond and
        show you the currently selected RONI range. To view the entirety of the data for the chosen
        station, select the extreme ends of the range slider to encompass all ENSO conditions.

        ###### The Map
        To select a station, zoom in to a station symbol of interest and click on it. The click will
        cause the graph to plot the data for that station and highlight the station in green. Hovering over
        a station shows its elevation and operator, its latest snow water equivalent, and its median for that
        date with the seasons the median is based on. Button controls in the upper left corner of the map
        (shown when the pointer is over the map) allow zooming in, zooming out, resetting the view or downloading
        an image of the map.

        ###### The Graph
        What is plotted on the graph is dictated by the other app elements and can also be controlled by
        interacting with the legends. The legend in the upper-left of the plot controls the
        presentation of the median and range curves for the station; the median entries give the number of
        complete seasons behind each median. The legend in the upper right adds other percentiles of the
        full record. The legend below the
        graph's axes controls the plotting of individual years. Clicking on a legend entry turns the element
        on or off. Double clicking turns all elements on or all but the clicked entry off. Finally, the graph and maps
        can both be zoomed into to modify the range of what is plotted. Additional controls in the upper right of
        the graph allow one to download an image of the current plot, reset the axes or choose a graph
        selection method.
        '''
    )

def footer_text_md(dcc):
    return dcc.Markdown(
        #'''
        #___
        '''
        #### Disclaimer
        This tool is intended for educational or entertainment purposes only. Official analysis of the snow and
        water supply status for British Columbia is available from the
        [BC River Forecast Centre](https://www2.gov.bc.ca/gov/content/environment/air-land-water/water/drought-flooding-dikes-dams/river-forecast-centre/snow-survey-water-supply-bulletin).
        The author makes no warranty
        nor is liable for anything associated with or resulting from the use of the app or the underlying data.
        No claims for data correctness or accuracy are made. This application is not affiliated with the Government
        of British Columbia, BC Hydro, Rio Tinto or Metro Vancouver.
        
        #### Author and Contact Information
        Faron Anslow
        <faron.anslow@gmail.com>
        '''
    )
