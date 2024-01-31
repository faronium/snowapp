## Multi-year Snow Water Equivalent Stratified by ENSO Strength

#### Introduction
There is a strong relationship between BC's weather in winter and spring and the state 
of the El Niño Southern Oscillation (ENSO) and this relationship translates to variability
in the province's snowpack from year to year. This app allows the exploration of that 
relationship between snow accumulation and ENSO in the province of British Columbia. 

#### Data sources
Snow water equivalent stations are maintained and operated by the [BC Ministry of Environment 
and Climate Change Strategy]
(https://www2.gov.bc.ca/gov/content/governments/organizational-structure/ministries-organizations/ministries/environment-climate-change) 
and its partners [BC Hydro](https://bchydro.com), [Rio Tinto](https://www.riotinto.com), and 
[Metro Vancouver](https://metrovancouver.org/). Data are collected using instruments called
snow pillows which weigh the overlying snow and that weight is converted to the water 
equivalent snow amount of the overlying snowpack. Data are daily and comprise a daily archive
through the previous water year (2023 at the time of this apps creation) and the continuously 
updated daily data for the most recent water year. The current-year snow data will have
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
either the OND or NDJ seasons of the year 2005, the ascribed year will be 2006.  
###### Individual Snow Seasons
The data from the individual years are presented as-is. As described above, the current year's data
is likely to have spurious values that have not been corrected by quality control software.

#### How-to
The primary component of this webpage is a graph that depicts the evolution of accumulated 
snow amount over the water year that runs from 1 October through 30 September in the 
subsequent year. User controls are a drop-down menu that provides a selection of snow measurement
locations organized by station identifiers grouped by snow catchment basins. The second control
is a slider located below the graph that allows for the selection of a range of values of the ENSO
strength as indicated by the Oceanic Niño Index. The third control is via the legend in the graph itself. 
Clicking on a legend entry turns the element on or off. Double clicking turns all elements on or off.
Finally, controls on the graph alow one to download an image of the current plot, reset the axes or choose
a graph selection method.

#### Discalimer
This tool is intended for educational or entertainment purposes only. The author makes no warrantee 
nor is liable for anything associated with or resulting from the use of the app or the underlying data. 
No claims for data correctness or accuracy are made. This application is not affiliated with the Government 
of British Columbia, BC Hydro, Rio Tinto or Metro Vancouver. 

#### Author and Contact Information
Faron Anslow
<faron.anslow@gmail.com>
___
