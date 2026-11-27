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


def test_flagged_seasons_are_dotted_labelled_and_unmarked():
    swe, row = season_and_row()
    matrix = pd.DataFrame({2002: swe, 2003: swe})
    ind = pd.DataFrame([row, row], index=[2002, 2003])
    fig = snowplot.snow_lineplot(matrix, [2003], [2002, 2003], 2026, 'red', 'red', 'title', indicators=ind,
                                 flagged={2002: 'Sensor fault.'})
    flagged = [t for t in fig.data if t.legendgroup == 'season-2002']
    assert len(flagged) == 1                                              # the line only, no markers
    assert flagged[0].name == '2002 (flagged)' and flagged[0].line.dash == 'dot'
    assert 'Sensor fault.' in flagged[0].hovertemplate
    assert any(t.legendgroup == 'season-2003' and t.mode == 'markers' for t in fig.data)


def test_estimated_stretches_are_shaded_and_noted():
    swe, row = season_and_row()
    flags = pd.Series(0, index=swe.index, dtype='int8'); flags.iloc[60:70] = 1; flags.iloc[200] = 2
    traces = snowplot.season_traces(swe.index, swe, 2002, '#636EFA', flags)
    shade, line = traces
    shaded = np.where(~np.isnan(np.asarray(shade.y, dtype=float)))[0]
    assert list(shaded) == list(range(59, 71)) + [199, 200, 201]       # each stretch plus a day either side
    assert 'straight line in the archive' in line.customdata[65] and line.customdata[10] == ''
    tr = snowplot.season_markers(swe, row, 2002, 'red', flags=flags)
    assert 'gap filled' in tr.text[2]                                   # fastest melt on day 200
