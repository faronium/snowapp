"""
Trend visualization functions for snow indicators

Author: Faron Anslow
E-mail: faron.anslow@gmail.com
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_indicator_timeseries(go, indicators, station_name, oni_data=None):
    '''
    Create a multi-panel timeseries plot showing all indicators for a single station.

    Parameters:
    -----------
    go : plotly.graph_objects module
    indicators : dict
        Dictionary of indicator DataFrames from compute_all_indicators()
    station_name : str
        Name of station to plot (must match column name in indicator DataFrames)
    oni_data : pandas.DataFrame, optional
        ONI data for coloring by ENSO phase

    Returns:
    --------
    fig : plotly Figure object
    '''
    # Create subplot figure with 5 rows
    fig = make_subplots(
        rows=5, cols=1,
        subplot_titles=(
            'Peak SWE Amount',
            'Peak SWE Timing',
            'Snow Season Start',
            'Snow Season End',
            'Peak Melt Rate'
        ),
        vertical_spacing=0.08,
        shared_xaxes=True
    )

    # Extract data for this station
    years = indicators['peak_amount'].index

    # Define ENSO colors if ONI data provided
    if oni_data is not None:
        colors = []
        for year in years:
            if year in oni_data.index:
                oni_val = oni_data.loc[year, 'ANOM']
                if oni_val > 0.5:
                    colors.append('rgb(255,110,95)')  # El Niño
                elif oni_val < -0.5:
                    colors.append('rgb(0,175,245)')  # La Niña
                else:
                    colors.append('rgb(128,128,128)')  # Neutral
            else:
                colors.append('rgb(128,128,128)')
    else:
        colors = 'rgb(70,130,180)'

    # Plot 1: Peak SWE Amount
    fig.add_trace(
        go.Scatter(
            x=years,
            y=indicators['peak_amount'][station_name],
            mode='lines+markers',
            marker=dict(size=6, color=colors),
            line=dict(color='rgb(70,130,180)', width=1),
            name='Peak SWE',
            showlegend=False
        ),
        row=1, col=1
    )

    # Plot 2: Peak SWE Timing
    fig.add_trace(
        go.Scatter(
            x=years,
            y=indicators['peak_timing'][station_name],
            mode='lines+markers',
            marker=dict(size=6, color=colors),
            line=dict(color='rgb(70,130,180)', width=1),
            name='Peak Timing',
            showlegend=False
        ),
        row=2, col=1
    )

    # Plot 3: Snow Season Start
    fig.add_trace(
        go.Scatter(
            x=years,
            y=indicators['snow_start'][station_name],
            mode='lines+markers',
            marker=dict(size=6, color=colors),
            line=dict(color='rgb(70,130,180)', width=1),
            name='Season Start',
            showlegend=False
        ),
        row=3, col=1
    )

    # Plot 4: Snow Season End
    fig.add_trace(
        go.Scatter(
            x=years,
            y=indicators['snow_end'][station_name],
            mode='lines+markers',
            marker=dict(size=6, color=colors),
            line=dict(color='rgb(70,130,180)', width=1),
            name='Season End',
            showlegend=False
        ),
        row=4, col=1
    )

    # Plot 5: Peak Melt Rate
    fig.add_trace(
        go.Scatter(
            x=years,
            y=indicators['peak_melt_rate'][station_name],
            mode='lines+markers',
            marker=dict(size=6, color=colors),
            line=dict(color='rgb(70,130,180)', width=1),
            name='Peak Melt Rate',
            showlegend=False
        ),
        row=5, col=1
    )

    # Update y-axis labels
    fig.update_yaxes(title_text="SWE (mm)", row=1, col=1)
    fig.update_yaxes(title_text="Day of Year", row=2, col=1)
    fig.update_yaxes(title_text="Day of Year", row=3, col=1)
    fig.update_yaxes(title_text="Day of Year", row=4, col=1)
    fig.update_yaxes(title_text="mm/day", row=5, col=1)

    # Update x-axis label (only on bottom plot)
    fig.update_xaxes(title_text="Hydrological Year", row=5, col=1)

    # Update layout
    fig.update_layout(
        height=1200,
        title_text=f"Snow Indicators Timeseries: {station_name}",
        showlegend=False,
        hovermode='x unified'
    )

    return fig


def create_indicator_oni_scatter(go, indicators, station_name, oni_data, indicator_name):
    '''
    Create scatter plot of a single indicator vs ONI for a station.

    Parameters:
    -----------
    go : plotly.graph_objects module
    indicators : dict
        Dictionary of indicator DataFrames
    station_name : str
        Station to plot
    oni_data : pandas.DataFrame
        ONI data with 'ANOM' column
    indicator_name : str
        Key in indicators dict ('peak_amount', 'peak_timing', etc.)

    Returns:
    --------
    fig : plotly Figure object
    '''
    # Get data for this station
    indicator_values = indicators[indicator_name][station_name]

    # Merge with ONI data
    combined = pd.DataFrame({
        'indicator': indicator_values,
        'year': indicator_values.index
    })
    combined = combined.merge(
        oni_data[['ANOM']],
        left_on='year',
        right_index=True,
        how='inner'
    )

    # Remove NaN values
    combined = combined.dropna()

    # Color by ENSO phase
    colors = []
    for oni_val in combined['ANOM']:
        if oni_val > 0.5:
            colors.append('rgb(255,110,95)')  # El Niño
        elif oni_val < -0.5:
            colors.append('rgb(0,175,245)')  # La Niña
        else:
            colors.append('rgb(128,128,128)')  # Neutral

    # Create scatter plot
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=combined['ANOM'],
            y=combined['indicator'],
            mode='markers',
            marker=dict(
                size=8,
                color=colors,
                line=dict(width=1, color='white')
            ),
            text=combined['year'],
            hovertemplate='<b>Year: %{text}</b><br>' +
                         'ONI: %{x:.2f}<br>' +
                         'Value: %{y:.1f}<br>' +
                         '<extra></extra>',
            showlegend=False
        )
    )

    # Add linear trend line
    if len(combined) > 2:
        z = np.polyfit(combined['ANOM'], combined['indicator'], 1)
        p = np.poly1d(z)
        x_trend = np.linspace(combined['ANOM'].min(), combined['ANOM'].max(), 100)
        y_trend = p(x_trend)

        fig.add_trace(
            go.Scatter(
                x=x_trend,
                y=y_trend,
                mode='lines',
                line=dict(color='black', width=2, dash='dash'),
                name='Trend',
                showlegend=True
            )
        )

        # Calculate correlation
        corr = combined['ANOM'].corr(combined['indicator'])
        corr_text = f"Correlation: {corr:.3f}"
    else:
        corr_text = ""

    # Indicator display names
    indicator_labels = {
        'peak_amount': 'Peak SWE (mm)',
        'peak_timing': 'Peak SWE Day of Year',
        'snow_start': 'Snow Season Start (Day of Year)',
        'snow_end': 'Snow Season End (Day of Year)',
        'peak_melt_rate': 'Peak Melt Rate (mm/day)',
        'peak_melt_timing': 'Peak Melt Timing (Day of Year)',
        'season_length': 'Snow Season Length (days)'
    }

    y_label = indicator_labels.get(indicator_name, indicator_name)

    fig.update_layout(
        title=f"{station_name}<br>{y_label} vs ONI<br><sub>{corr_text}</sub>",
        xaxis_title="Oceanic Niño Index (ONI)",
        yaxis_title=y_label,
        hovermode='closest',
        height=500
    )

    return fig


def create_multi_indicator_oni_scatter(go, indicators, station_name, oni_data):
    '''
    Create a multi-panel scatter plot showing all indicators vs ONI for a single station.

    Parameters:
    -----------
    go : plotly.graph_objects module
    indicators : dict
        Dictionary of indicator DataFrames
    station_name : str
        Station to plot
    oni_data : pandas.DataFrame
        ONI data with 'ANOM' column

    Returns:
    --------
    fig : plotly Figure object
    '''
    indicator_list = [
        ('peak_amount', 'Peak SWE (mm)'),
        ('peak_timing', 'Peak Timing (DOY)'),
        ('snow_start', 'Season Start (DOY)'),
        ('snow_end', 'Season End (DOY)'),
        ('peak_melt_rate', 'Peak Melt (mm/day)'),
        ('season_length', 'Season Length (days)')
    ]

    # Create subplot figure
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=[label for _, label in indicator_list],
        vertical_spacing=0.12,
        horizontal_spacing=0.12
    )

    for idx, (indicator_name, label) in enumerate(indicator_list):
        row = idx // 2 + 1
        col = idx % 2 + 1

        # Get data
        indicator_values = indicators[indicator_name][station_name]
        combined = pd.DataFrame({
            'indicator': indicator_values,
            'year': indicator_values.index
        })
        combined = combined.merge(
            oni_data[['ANOM']],
            left_on='year',
            right_index=True,
            how='inner'
        )
        combined = combined.dropna()

        if len(combined) == 0:
            continue

        # Color by ENSO phase
        colors = []
        for oni_val in combined['ANOM']:
            if oni_val > 0.5:
                colors.append('rgb(255,110,95)')
            elif oni_val < -0.5:
                colors.append('rgb(0,175,245)')
            else:
                colors.append('rgb(128,128,128)')

        # Add scatter
        fig.add_trace(
            go.Scatter(
                x=combined['ANOM'],
                y=combined['indicator'],
                mode='markers',
                marker=dict(size=6, color=colors, line=dict(width=0.5, color='white')),
                text=combined['year'],
                hovertemplate='Year: %{text}<br>ONI: %{x:.2f}<br>%{y:.1f}<extra></extra>',
                showlegend=False
            ),
            row=row, col=col
        )

        # Add trend line
        if len(combined) > 2:
            z = np.polyfit(combined['ANOM'], combined['indicator'], 1)
            p = np.poly1d(z)
            x_trend = np.linspace(combined['ANOM'].min(), combined['ANOM'].max(), 50)
            y_trend = p(x_trend)

            fig.add_trace(
                go.Scatter(
                    x=x_trend,
                    y=y_trend,
                    mode='lines',
                    line=dict(color='rgba(0,0,0,0.3)', width=1.5, dash='dash'),
                    showlegend=False
                ),
                row=row, col=col
            )

    # Update layout
    fig.update_xaxes(title_text="ONI", row=3, col=1)
    fig.update_xaxes(title_text="ONI", row=3, col=2)

    fig.update_layout(
        height=900,
        title_text=f"Snow Indicators vs ONI: {station_name}",
        showlegend=False,
        hovermode='closest'
    )

    return fig
