import json

from bokeh.io import output_file, show, curdoc
from bokeh.models import GeoJSONDataSource, Range1d, CheckboxGroup, RadioGroup
from bokeh.models import ColumnDataSource, Slider, TextInput, DateSlider, Paragraph, HoverTool
from bokeh.layouts import column, row
from bokeh.plotting import figure
from bokeh.transform import factor_cmap
from bokeh.palettes import d3
import geopandas as gpd
import pandas as pd
from datetime import datetime, date, timedelta
import numpy as np
from collections import OrderedDict
from dateutil.relativedelta import relativedelta

MAPS_1938 = r'clean_1938_maps_2pt.geojson'
GERMAN_BORDERS = r'german_borders.gpkg'
CAMPS='clean_ss_camps_2pt_v2.gpkg'
_crs = "+proj=tpeqd +lat_1=48 +lon_1=2 +lat_2=48 +lon_2=21"

# Data sources ---------------------------------------------------------------------------------------------------------
# Load 1938 European map data
with open(MAPS_1938,'r') as f:
    data=json.load(f)
_gsrc_1938 = GeoJSONDataSource(geojson=json.dumps(data))

# Load the map borders
_gdf_german_borders = gpd.read_file(GERMAN_BORDERS)
if isinstance(_gdf_german_borders['date'].loc[0],str):
    _gdf_german_borders['date'] = pd.to_datetime(_gdf_german_borders['date'],format='%Y-%m-%dT%H:%M:%S')

# Load camp data
_geo_ss = gpd.read_file(CAMPS)
if isinstance(_geo_ss['DATE_OPEN'].loc[0],str):
    _geo_ss['DATE_OPEN'] = pd.to_datetime(_geo_ss['DATE_OPEN'],format='%Y-%m-%dT%H:%M:%S')
    _geo_ss['DATE_CLOSE'] = pd.to_datetime(_geo_ss['DATE_CLOSE'], format='%Y-%m-%dT%H:%M:%S')
_geo_ss_dated = _geo_ss.dropna(subset=['DATE_OPEN', 'DATE_CLOSE'])

function_map = {0.0: 'No labor',
                1.0: 'Unspecified',
                2.0: 'Building material',
                3.0: 'Construction',
                4.0: 'Armaments',
                5.0: 'Manufacturing (non-armament)',
                6.0: 'Camp construction',
                7.0: 'Defense construction',
                8.0: 'Collection of sick/dying',
                9.0: 'Oil and coal production',
                10.0: 'Extermination',
                11.0: 'Material transport'}
function_color_map = dict(zip(list(function_map.values()), d3['Category20'][len(function_map.values())]))

# Create additional column with firm names to show
n_firms_to_keep=12
firms_to_keep = _geo_ss_dated.FIRMABBREV.value_counts().index.to_list()[:n_firms_to_keep]
def firms_filter(x):
    if x is None:
        return 'Unknown'
    elif x in firms_to_keep:
        return x
    else:
        return 'other'
_geo_ss_dated = _geo_ss_dated.assign( firm_to_show = _geo_ss_dated.FIRMABBREV.apply( firms_filter ) )
firm_color_map = dict( zip(_geo_ss_dated.firm_to_show.value_counts().index.to_list(), d3['Category20'][n_firms_to_keep+2]))
firm_color_map['Unknown'] = '#d3d3d3'

# Camps position storage
_src_camps = ColumnDataSource(data=dict(x=[], y=[], size=[], color=[], legend=[], main=[], subcamp = [],
                                        peak_pop= [], nations=[], labor=[]))

# Data source for German camp borders
mp = _gdf_german_borders.loc[0].geometry
geojson = gpd.GeoSeries([mp]).__geo_interface__
_gsrc_borders = GeoJSONDataSource(geojson=json.dumps(geojson))

# Setup widgets --------------------------------------------------------------------------------------------------------
# Map plot

p = figure(background_fill_color="white",plot_height = 800, plot_width = 1200, match_aspect=True,
           title="German concentration camps during WWII", title_location="above")
p.x_range = Range1d(-1.25E6,1.5E6)
p.y_range = Range1d(-0.5e6,1.5e6)
p.title.align = "center"
p.title.text_color = "black"
p.title.text_font_size = "25px"

p.xaxis.major_tick_line_color = None  # turn off x-axis major ticks
p.xaxis.minor_tick_line_color = None  # turn off x-axis minor ticks
p.yaxis.major_tick_line_color = None  # turn off y-axis major ticks
p.yaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
p.xaxis.major_label_text_font_size = '0pt'  # turn off x-axis tick labels
p.yaxis.major_label_text_font_size = '0pt'  # turn off y-axis tick labels
p.outline_line_color = 'black'

# Date slider
slider_date = DateSlider(title="Date", value=date(1939, 1, 1), start=date(1939, 1, 1), end=date(1946, 1, 1),
                         step=7*24*3600*1000,margin = (5, 45, 5, 25))
# slider_date = DateSlider(title="Date", value_throttled=date(1939, 1, 1), start=date(1939, 1, 1), end=date(1946, 1, 1),
#                          step=7*24*3600*1000,margin = (5, 45, 5, 25))

# Option check boxes
check_button_label = Paragraph(text="Options", height=20)
check_button_labels = ['Symbol size by camp population','Show German occupied areas (available till August 1944)']
check_buttons = OrderedDict(zip(['population_size','german_borders'],list(range(len(check_button_labels)))))
checkbox_options = CheckboxGroup(labels=check_button_labels, active=[])

radio_color_by_label = Paragraph(text="Symbol color", height=20)
radio_buttons_labels = ['Fixed', 'By function','By firm']
radio_buttons = OrderedDict(zip(radio_buttons_labels,list(range(len(radio_buttons_labels)))))
radio_color_by = RadioGroup(labels=radio_buttons_labels, active=0)

# Check boxes

# Do initial plotting --------------------------------------------------------------------------------------------------
# Countries
countries = p.patches('xs','ys', source = _gsrc_1938,
                      line_color = 'black',
                      line_width = 0.50,
                      fill_color = 'white',
                      fill_alpha = 1)

country_tooltips = [
    ("Country", "@ABBREVNAME"),
]
countries_hover = HoverTool(renderers = [countries], tooltips = country_tooltips)
p.add_tools(countries_hover)

# German war borders.
german_borders = p.patches('xs','ys',source = _gsrc_borders,
                           line_color='red',
                           line_width=1.50,
                           fill_color='none',
                           fill_alpha=0.5)
german_borders.visible = False

# Camps
# camps = p.circle('x', 'y', size=5, fill_color="#21a7df", fill_alpha=0.5,source=_src_camps)
camps = p.scatter('x', 'y', size='size', color='color', fill_alpha=0.5,source=_src_camps,
                  legend_field='legend')

camp_tooltips = [
    ("Name", "@subcamp"),
    ("Subcamp of", "@main"),
    ("Peak population", "@peak_pop"),
    ("Nations", "@nations"),
    ("Labor", "@labor"),
]
camps_hover = HoverTool(renderers = [camps], tooltips = camp_tooltips)
p.add_tools(camps_hover)

p.legend.location = "top_left"

# Update functions -----------------------------------------------------------------------------------------------------
def get_slider_date():
    # Get the slider date as a datetime object
    return datetime(1970, 1, 1) + timedelta(milliseconds=slider_date.value)
    # return datetime(1970, 1, 1) + timedelta(milliseconds=slider_date.value_throttled)

def update_camps(attrname, old, new):

    # Update the plot
    t_cutoff = get_slider_date()
    geo_ss_plot = _geo_ss_dated[(_geo_ss_dated['DATE_OPEN'] < t_cutoff) & (_geo_ss_dated['DATE_CLOSE'] > t_cutoff)]
    geo_ss_plot = geo_ss_plot.to_crs(_crs)

    camp_x, camp_y, size = [], [], []
    for point in geo_ss_plot['geometry']:
        camp_x.append(point.x)
        camp_y.append(point.y)

    # symbol_size = (np.log10(np.maximum(1.0, _geo_ss_dated.PEAK_POP.to_numpy()))+1)*2.5
    if check_buttons['population_size'] in checkbox_options.active:
        symbol_size = 0.15*(np.sqrt(geo_ss_plot.PEAK_POP.to_numpy())+10)
    else:
        symbol_size = 5 * np.ones((geo_ss_plot.shape[0],))

    if check_buttons['german_borders'] in checkbox_options.active and t_cutoff < datetime(1944,8,1):
        ix_min = (_gdf_german_borders.date - t_cutoff).abs().idxmin()
        mp = _gdf_german_borders.iloc[ix_min].geometry
        geojson = gpd.GeoSeries([mp]).__geo_interface__
        _gsrc_borders.geojson = json.dumps(geojson)
        german_borders.visible = True

        # if t_cutoff > datetime(1944,8,1):
        #     german_borders.glyph.line_color='#FF91A4'
        # else:
        #     german_borders.glyph.line_color='red'
    else:
        german_borders.visible = False

    if radio_color_by.active==radio_buttons['Fixed']:
        color_by = geo_ss_plot.shape[0] * [ '#aec7e8' ]
        legend_entries = geo_ss_plot.shape[0] * ['NA']
        p.legend.visible = False
    elif radio_color_by.active==radio_buttons['By function']:
        function_names_series = geo_ss_plot.FUNC_1.map(function_map)
        legend_entries = function_names_series.to_list()
        color_by = function_names_series.map(function_color_map).to_list()
        p.legend.visible = True
    elif radio_color_by.active==radio_buttons['By firm']:
        legend_entries = geo_ss_plot.firm_to_show.to_list()
        color_by = geo_ss_plot.firm_to_show.map(firm_color_map).to_list()
        p.legend.visible = True
    else:
        raise RuntimeError()

    _src_camps.data = dict(x=camp_x, y=camp_y, size=symbol_size,
                           color=color_by, legend=legend_entries,
                           main=geo_ss_plot.MAIN.to_list(), subcamp = geo_ss_plot.SUBCAMP.to_list(),
                           peak_pop = geo_ss_plot.PEAK_POP.to_list(),
                           nations = geo_ss_plot.NATIONS.to_list(),
                           labor = geo_ss_plot.LABOR.to_list())

# slider_date.value = (date(1944,1,1) - date(1970,1,1)).total_seconds()*1000
slider_date.on_change('value_throttled', update_camps)
checkbox_options.on_change('active', update_camps)
radio_color_by.on_change('active',update_camps)

update_camps('','','')

figure_col = column(p, slider_date)
vertical_spacer = Paragraph(text="  ", height=40, width=50)

controls_col = column(vertical_spacer, check_button_label, checkbox_options, radio_color_by_label, radio_color_by)

spacer = Paragraph(text="  ", height=20, width=50)

curdoc().add_root(row(figure_col, spacer, controls_col))
curdoc().title = "SS camps"
