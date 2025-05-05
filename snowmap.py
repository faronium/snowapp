def draw_station_map(go,locdfuse,anomstat):
    '''
    Function to draw a map of data from the location dataframe locdfuse using mapbox
    map tiles. This function was offloaded from the main snowapp code
    to lighten it up. May opt to pass in some styling at a later date, but for now
    this serves the purpose.
    '''
    fig = go.Figure()
    if anomstat:
        markeruse = go.scattermap.Marker(
                size = 18,
                colorscale='RdBu',
                color = locdfuse['pct_snow'],  #'rgba(0,175,245,0.7)'
                opacity = 1.,
                cmin = 25.,
                cmax = 175.,
                cmid = 100.,
            )
    else:
        markeruse = go.scattermap.Marker(
                size = 18,
                color = 'rgba(0,175,245,0.7)',
                opacity = 1.,
                cmin = 25.,
                cmax = 175.,
                cmid = 100.,
            )
    fig.add_trace(
        go.Scattermap(
            lon = locdfuse['LONGITUDE'],
            lat = locdfuse['LATITUDE'],
            text = locdfuse['text'],
            mode = 'markers',
            customdata=locdfuse[['LCTN_NM','LCTN_ID','ELEVATION','pct_snow']],
            hovertemplate="<b>%{customdata[0]}</b><br><br>"+
            "Station ID: %{customdata[1]}<br>"+
            "Elevation: %{customdata[2]}<br>"+
            "Current Anomaly: %{customdata[3]:.2f}"+
            "<extra></extra>",
            marker=markeruse,
            selected = dict(
                marker = {
                    'size': 26,
                    'color': 'rgba(0,250,131,0.75)',
                }
            ),
        )
    )
    fig.update_layout(
        clickmode = 'event+select',
        map = {
            'zoom': 3,
            'center': dict(
                         lat=52.5,
                         lon=-126
                      ),
            'style': 'open-street-map',
            
        },
        margin = dict(l=0, r=0, b=0, t=0),
        map_bounds = {"west": -142, "east": -110, "south": 45, "north": 61},
        hoverlabel=dict(
            bgcolor="white",
            font_size=14,
        )
     )

    return fig
