def draw_station_map(go,locdfuse):
    '''
    Function to draw a map of data from the location dataframe locdfuse using mapbox
    map tiles. This function was offloaded from the main snowapp code
    to lighten it up. May opt to pass in some styling at a later date, but for now
    this serves the purpose.
    '''
    token = open(".mapbox_token").read()
    fig = go.Figure()
    fig.add_trace(
        go.Scattermapbox(
            lon = locdfuse['LONGITUDE'],
            lat = locdfuse['LATITUDE'],
            text = locdfuse['text'],
            mode = 'markers',
            marker=go.scattermapbox.Marker(
                size = 16,
                color = 'rgba(0,175,245,0.7)',     #locdf['ELEVATION'],
            ),
            selected = go.scattermapbox.Selected(
                marker = {
                    'size': 26,
                    'color': 'rgba(255,110,95,0.99)',
                }
            ),
        )
    )
    fig.update_layout(
        #title_text = 'test snow sites',
        clickmode = 'event+select',
        mapbox = {
            'accesstoken': token,
            'style': 'outdoors',
            'zoom': 3,
            'center': go.layout.mapbox.Center(
                         lat=54.5,
                         lon=-126
                      ),
        },
     )
    fig.update_layout(
        margin = dict(l=0, r=0, b=0, t=0),
        mapbox_bounds = {"west": -142, "east": -110, "south": 45, "north": 63},
        #width=600, 
        #height=600
    )
    #fig.update_traces(cluster=dict(enabled=True))
    return fig
