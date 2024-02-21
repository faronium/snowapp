
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
        and Climate Change Strategy]
        (https://www2.gov.bc.ca/gov/content/environment/air-land-water/water/water-science-data/water-data-tools/snow-survey-data)
        and its partners [BC Hydro](https://bchydro.com), [Rio Tinto](https://www.riotinto.com), and
        [Metro Vancouver](https://metrovancouver.org/). Data are collected using instruments called
        snow pillows which weigh the overlying snow and that weight is converted to the water
        equivalent content of the snowpack. Data are daily and comprise a daily archive
        through the previous water year (2023 at the time of this app's creation) and the continuously
        updated daily data for the most recent water year. The current-year snow data may have
        quality artifacts because the data have not been quality controlled. Oceanic Niño Index (ONI) is produced
        by the US National Oceanic and Atmospheric Administration's [Climate Prediction Center]
        (https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php). The index is based
        on sea surface temperature anomalies in the Niño 3.4 region of the tropical Pacific Ocean.

        #### Analysis
        ###### Snow Ranges
        The primary elements of the plot are median snow water equivalent grouping by day of the hydrological year
        and range about that median expressed as one standard deviation of the data for that hydrological day.
        A trace and range are shown for each of the full record (in grey) and for the record subset by the selected
        ENSO strength colorized with reds showing selections with ENSO positive (El Niño) overall and
        blues for selections with ENSO negative (La Niña). For example, if the ONI range is -0.5 to 2, the
        midpoint of the range is 1.25 and thus the plot of the subset will be red in color.
        ###### The Oceanic Niño Index
        The Oceanic Niño Index for a given year is taken as the extrema for the winter season of interest.
        The underlying ONI data are over three-month periods and incorporate the seasons OND through MAM.
        Rules for the hydrological year are applied. So, for example, if the extrema of the ONI falls in
        either the OND or NDJ seasons of the year 2005, the ascribed year will be 2006. The slider element
        of the app is labelled with subjective ENSO strengths. These are mapped to ONI as follows:

        * -0.5 to 0.5 is ENSO neutral
        * -1.3 or 1.3 are mapped as moderate events
        * -2.7 or 2.7 are mapped as extreme events.

        ONI is resolved and may be selected at 0.1 degree increments.
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

        * a **checklist** in the upper left to subset data to that with current year data and that with more than 20 years;
        * a **slider** in the upper right that allows for the selection of a range of values of the ENSO strength;
        * a **map** that shows the location of snow-pillow sites in BC;
        * a **graph** that plots the snow water equivalent for the hydrological year.

        ###### The Checklist
        The checklist contains two items whose selection causes the stations available for plotting to be
        subset. By default, the *Require current year?* option is selected to show stations that have data for
        the current year. The second option allows the restriction of available data to those stations with 20 or more
        years of record. Furthermore, a station is considered to have data for a given year only if the timeseries
        more than 80% complete. These longer, more complete records are recommended for investigating the ENSO/snow
        relationship for a given station.

        ###### The ENSO Slider
        The slider allows for the selection of a range of values of the ENSO strength as
        determined by the Oceanic Niño Index. Click and drag the handles or click on the slider
        bar and the range will adjust to your input. The **graph** title will respond and
        show you the currently selected ONI range. To view the entirety of the data for the chosen
        station, select the extreme ends of the range slider to encompass all ENSO conditions.

        ###### The Map
        To select a station, zoom in to a station symbol of interest and click on it. The click will
        cause the graph to plot the data for that station and highlight the station in red. There
        are four button controls in the upper right corner of the map that allow downloading an
        image of the current map, zooming in, zooming out or resetting the axes.

        ###### The Graph
        What is plotted on the graph is dictated by the other app elements and can also be controlled by
        interacting with the two legends. The legend in the upper-left of the plot controls the
        presentation of the median and range curves for the station. The legend below the
        graph's axes controls the plotting of individual years. Clicking on a legend entry turns the element
        on or off. Double clicking turns all elements on or all but the clicked entry off. Finally, the graph and maps
        can both be zoomed into to modify the range of what is plotted. Additional controls in the upper right of
        the graph alow one to download an image of the current plot, reset the axes or choose a graph
        selection method.
        ___
        '''
    )

def footer_text_md(dcc):
    return dcc.Markdown(
        '''
        ___
        #### Author and Contact Information
        Faron Anslow
        <faron.anslow@gmail.com>

        #### Disclaimer
        This tool is intended for educational or entertainment purposes only. Official analysis of the snow and
        water supply status for British Columbia is available from the
        [BC River Forecast Centre](https://www2.gov.bc.ca/gov/content/environment/air-land-water/water/drought-flooding-dikes-dams/river-forecast-centre/snow-survey-water-supply-bulletin).
        The author makes no warranty
        nor is liable for anything associated with or resulting from the use of the app or the underlying data.
        No claims for data correctness or accuracy are made. This application is not affiliated with the Government
        of British Columbia, BC Hydro, Rio Tinto or Metro Vancouver.
        '''
    )
