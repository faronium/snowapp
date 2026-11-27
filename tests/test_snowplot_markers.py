import numpy as np
import pandas as pd

import snowplot
import snowindicators as si
from snowdata import PLOT_DAYS


def season_and_row():
    labels = pd.date_range('2001-10-01', periods=365).strftime('%m-%d')
    swe = pd.Series(np.r_[np.zeros(30), np.linspace(0, 500, 150), np.linspace(500, 0, 60), np.zeros(125)], index=labels)
    row = pd.Series({'snow_on_day': 31, 'peak_day': 179, 'peak_swe': 498.0, 'melt_day': 200, 'melt_rate': 8.3,
                     'snow_off_day': 240})
    return swe, row


def test_markers_sit_on_the_line_at_each_date():
    swe, row = season_and_row()
    tr = snowplot.season_markers(swe, row, 2002, 'red')
    assert list(tr.x) == [swe.index[31], swe.index[179], swe.index[200], swe.index[240]]
    assert list(tr.y) == [swe.iloc[31], swe.iloc[179], swe.iloc[200], swe.iloc[240]]
    assert list(tr.marker.symbol) == ['triangle-up', 'diamond', 'triangle-down', 'square']
    assert '498 mm on 29 Mar' in tr.text[1] and '8.3 mm/day around 19 Apr' in tr.text[2]


def test_missing_and_out_of_range_dates():
    swe, row = season_and_row()
    row = row.copy(); row['snow_on_day'] = -5; row['melt_day'] = np.nan; row['snow_off_day'] = PLOT_DAYS + 3
    tr = snowplot.season_markers(swe.iloc[:PLOT_DAYS], row, 2002, 'red')
    assert list(tr.x) == [swe.index[0], swe.index[179]]          # September snow-on at 1 Oct; no melt, off past the plot
    assert 'before 1 Oct' in tr.text[0] and '26 Sep' in tr.text[0]


def test_markers_share_the_season_legend_group():
    swe, row = season_and_row()
    matrix = pd.DataFrame({2002: swe, 2003: swe})
    ind = pd.DataFrame([row], index=[2002])
    fig = snowplot.snow_lineplot(matrix, [2002, 2003], [2002, 2003], 2026, 'red', 'red', 'title', indicators=ind)
    groups = [(t.name, t.legendgroup, t.mode, t.visible) for t in fig.data if t.legendgroup and t.legendgroup.startswith('season-')]
    assert ('2002', 'season-2002', None, 'legendonly') in groups
    assert (None, 'season-2002', 'markers', 'legendonly') in groups
    assert not any(g[1] == 'season-2003' and g[2] == 'markers' for g in groups)   # no indicators, no markers
