
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
        Medians, ranges and the snow season indicators are calculated only from *complete* seasons: past water
        years with data on at least 95% of the days from 1 October to 1 July. The window ends on 1 July so that
        lower, warmer stations that melt out early still qualify. The current season is never included. The
        legend on the graph and the station details on the map give the number of complete seasons and the
        years they span, which differ from station to station.
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

        #### Snow Season Indicators (Trends tab)
        For each complete season at a station:

        * **Peak SWE** and **peak date**: the highest 5-day running mean of snow water equivalent, as measured.
        * **Snow-on** and **snow-off dates**: the first day of, and the first day after, the longest continuous
          period with snow water equivalent at least 10 mm above bare ground. The search starts on 1 September,
          because snow arrives before 1 October at some high stations. Short gaps in the data count as snow
          when there is snow on both sides.
        * **Season length**: the days from snow-on to snow-off.
        * **Peak melt rate**: the largest 5-day mean daily loss of snow water equivalent between the peak and
          snow-off.

        *Bare ground.* Some snow pillows read a steady value above zero when there is no snow, usually after a
        recalibration. The bare-ground level is taken from flat stretches of the record (a 7-day standard
        deviation under 2 mm) in the July to September before the season (for snow-on) and after it (for
        snow-off). A flat level of 100 mm or more, or one that is both 10 mm or more and a quarter or more of
        the season's peak, cannot be bare ground and points to a sensor fault, so the dates that depend on it
        are left out.

        Each value needs data around it (for example, an observed snow-free day just before snow-on), and is
        left out of the plots when that is missing.

        *Statistics.* A trend is the Theil-Sen slope (the median of the slopes between every pair of seasons),
        given per decade, with the two-sided Mann-Kendall test for its significance. The relationship with ENSO
        is a least-squares line against each water year's RONI value, with the Pearson correlation and an
        approximate two-sided p-value. Both are shown only for indicators with at least 10 seasons, and lines
        are solid when p < 0.05. Points are coloured by the water year's ENSO phase (RONI of +0.5 or more is
        El Niño, -0.5 or less is La Niña).

        #### Grouped Stations (Trends tab)
        A single station's record is often too short and too variable for a trend to stand out. The Trends tab
        can instead combine a station with others nearby: its **sub-basin** (stations whose codes share the
        first two characters, such as 2D), its **region** (the first character, such as 2), or **all of BC**.

        ###### The regional series
        Each indicator value is treated as *station level + year effect*, and both are estimated together by
        least squares from all the stations in the group. The year effects form the regional series: how much
        earlier or later, or larger or smaller, that season was across the group. Each station's typical level
        is removed, so a high, snowy station and a low one can be combined.

        The levels are estimated together, rather than taking each station's own average or standardizing it
        to z-scores, because stations cover different years. A station that only reports in recent decades has
        an average from those recent years alone; anomalies from that average would pull the regional series
        toward zero in exactly the years it reports, and dilute any trend. Fitted together, the station is
        compared with the others in the years they share. Stations whose years never overlap with the rest of
        the group are left out.

        Dates and season length are combined in days, so results read as *days earlier or later than normal*.
        Peak snow water equivalent and melt rate are combined on a logarithmic scale, so a year's value is a
        ratio (*35% below normal*) and large and small snowpacks count in proportion. *Normal* is the group's
        average over its record. A station needs at least 5 seasons of an indicator to be included, and a year
        enters the regional series only if at least 2 stations reported it. Each station's own values, relative
        to its level, are shown as faint grey points behind the regional series.

        ###### Trends for a group
        Stations in a group share most of their year-to-year variation; for snow-off date and peak snow water
        equivalent, stations in the same sub-basin typically correlate at about 0.7 to 0.8 from year to year.
        Their records are therefore far from independent, and treating every station-season as a separate
        observation would greatly overstate significance. The trend is tested with the **Regional Kendall
        test** (Helsel and Frans, 2006), which adds up the Mann-Kendall statistic across stations and corrects
        its variance for the correlation between them (Dietz and Killeen, 1981, with missing years handled as
        in Hirsch and Slack, 1984). The regional slope is the median of the slopes between every pair of
        seasons within each station, pooled over the group, and is given per decade (in % per decade for snow
        water equivalent and melt rate). Grouping helps most for the noisier indicators (peak date, snow-on
        date and melt rate) and by joining records that cover different periods into a longer one.

        ###### ENSO relationship for a group
        The regional series is compared with each water year's RONI using a least-squares line and the Pearson
        correlation, with one value per year.

        ###### Removing the ENSO signal
        With *Remove the ENSO (RONI) signal before testing trends* ticked, the part of each year's value
        explained by that year's RONI (from the least-squares fit above, or the station's own fit for a single
        station) is subtracted before the trend is tested. Much of the year-to-year variation in BC snow is
        tied to ENSO, so removing it can reveal a smaller trend underneath. The result is the trend that is not
        explained by year-to-year ENSO variability; if the mix of El Niño and La Niña years changed over the
        record, this trend can differ from the plain one.

        ###### The trend period and the growing network
        The network of snow pillows has grown a great deal: across BC, about 2 stations reported in 1970,
        5 in 1980, 17 in 1990, 44 in 2000 and more than 80 today, and regions 3 and 4 begin only around 1990.
        Before 1990 a regional value rests on a handful of stations, and the long records of those few early
        stations would carry much of the weight in a full-record trend. Trends are therefore calculated **since
        1990** by default, when the network became large enough to represent the province; *Full record* uses
        every season instead. In the group views, the bar chart along the bottom shows how many stations
        contributed each year (lighter bars are years with too few stations to enter the regional series),
        and larger markers show years that more stations reported.

        *Same stations throughout* keeps only the stations that reported at least 80% of the seasons in the
        period, so that the make-up of the regional series cannot drift as stations open and close. It uses
        fewer stations but compares like with like.

        Snow in BC also varies from decade to decade with the Pacific Decadal Oscillation. Removing the ENSO
        signal does not remove this slower variation, so a trend over a few decades can change noticeably with
        the period chosen. The record is not always a straight line: across BC, snow-off dates moved earlier
        through the 1970s and 1980s, jumped later around 1990, and have moved earlier again since. A single
        trend over the full record is smaller than the trend within either part.

        ###### Caveats
        Groups mix stations at different elevations, which can respond differently to a warming climate. The
        stations in a group change over time as stations open and close. With six indicators and many groups,
        some results will reach p < 0.05 by chance, so a single significant result should be read with care.

        ###### References
        Dietz, E.J. and Killeen, T.J. (1981). A nonparametric multivariate test for monotone trend with
        pharmaceutical applications. *Journal of the American Statistical Association*, 76, 169-174.

        Helsel, D.R. and Frans, L.M. (2006). Regional Kendall test for trend. *Environmental Science &
        Technology*, 40, 4066-4073.

        Hirsch, R.M. and Slack, J.R. (1984). A nonparametric trend test for seasonal data with serial
        dependence. *Water Resources Research*, 20, 727-732.

        Sen, P.K. (1968). Estimates of the regression coefficient based on Kendall's tau. *Journal of the
        American Statistical Association*, 63, 1379-1389.
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

        ###### The Trends Tab
        The Trends tab shows snow season indicators (peak snow, snow-on and snow-off dates, season length and
        peak melt rate). Choose a station from the list, or click it on the map of the main tab. Under *Show*,
        pick that station alone or combine it with the other stations in its sub-basin, its region, or all of
        BC. *Indicators by water year* shows each indicator over time with its trend; *Indicators vs RONI*
        shows each one against the strength of El Niño or La Niña that year. Ticking *Remove the ENSO (RONI)
        signal before testing trends* tests for a trend in what is left after the ENSO influence is taken out
        (it applies to *Indicators by water year*, and is greyed out for *Indicators vs RONI*). *Period* sets
        the seasons used: since 1990 (the default) or the full record. For groups, *Same stations throughout*
        keeps only stations that reported in nearly every season of the period.
        The definitions and statistics are described on the Analysis tab.

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
