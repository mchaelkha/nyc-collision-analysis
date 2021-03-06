# ============================================================== #
#  SECTION: Imports                                              #
# ============================================================== #

# standard library
from collections import defaultdict
from datetime import datetime

# third party library
import numpy as np
import pandas as pd
from pandas.api.types import CategoricalDtype
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
from mpl_toolkits.basemap import Basemap
import seaborn as sns
from PIL import Image

# local


# ============================================================== #
#  SECTION: Globals                                              #
# ============================================================== #

# CSV of motor vehicle collisions
MOTOR_VEHICLE_COLLISIONS_CSV = 'Motor_Vehicle_Collisions_-_Crashes.csv'

# preprocessed cleaned vehicle colision file
CLEAN_MOTOR_VEHICLE_COLLISIONS_CSV = 'Clean_Motor_Vehicle_Collisions_-_Crashes.csv'

# ============================================================== #
#  SECTION: Class Definitions                                   #
# ============================================================== #


# ============================================================== #
#  SECTION: Helper Definitions                                   #
# ============================================================== #

# mapping of borough to its latitude and longitude
BOROUGH_COORDS = {
    'STATEN ISLAND': (40.58, 74.15),
    'BRONX': (40.84, 73.86),
    'QUEENS': (40.73, 73.79),
    'MANHATTAN': (40.78, 73.97),
    'BROOKLYN': (40.68, 73.94)
}

# mapping of borough to its min, max latitude and longitude
BOROUGH_BOUNDS = {
    'STATEN ISLAND': ((40.500084, -74.249940), (40.648273, -74.060880)),
    'BRONX': ((40.785124, -73.934663), (40.914714, -73.765061)),
    'QUEENS': ((40.541444, -73.961150), (40.800279, -73.699538)),
    'MANHATTAN': ((40.701239, -74.019387), (40.877565, -73.910405)),
    'BROOKLYN': ((40.571755, -74.041960), (40.740757, -73.861229))
}

# mapping of borough boundaries for the density heat map
BOROUGH_EXTENT = {
    'STATEN ISLAND': (-74.249940, -74.060880, 40.500084, 40.648273),
    'BRONX': (-73.934663, -73.782936, 40.785124, 40.912884),
    'QUEENS': (-73.959744, -73.700550, 40.554388, 40.800262),
    'MANHATTAN': (-74.017940, -73.911230, 40.701256, 40.872917),
    'BROOKLYN': (-74.040820, -73.861230, 40.572006, 40.738853)
}

# min latitude of NYC
MIN_LATITUDE = 40.49
# max latitude of NYC
MAX_LATITUDE = 40.92

# min, max longitude of NYC
MIN_LONGITUDE = -74.25
MAX_LONGITUDE = -73.7

# range of selected years
YEARS = range(2013, 2021)

# selected months
MONTHS = {
    1: 'January',
    2: 'February',
    3: 'March',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'August',
    9: 'September',
    10: 'October',
    11: 'November',
    12: 'December'
}

# range of days
DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

# range of hours, military time
HOURS = range(0, 24)


def df_filter_by(df, column, value):
    """
    Returns a dataframe with rows selected from df that have value within column.
    """
    if column == 'borough':
        return df[df['BOROUGH'] == value]
    elif column == 'year':
        return df[df['CRASH TIME'].dt.year == value]
    elif column == 'month':
        return df[df['CRASH TIME'].dt.month == value]
    elif column == 'day':
        return df[df['CRASH TIME'].dt.day_name() == value]
    elif column == 'hour':
        return df[df['CRASH TIME'].dt.hour == value]


def df_between_coords(df, coord1, coord2):
    """
    Filter dataframe by being between two coordinates, c1 and c2.
    """
    # min, max latitude and longitude of coord1
    min_lat, min_long = coord1
    # min, max latitude and longitude of coord2
    max_lat, max_long = coord2
    within_lat = (min_lat < df['LATITUDE']) & (df['LATITUDE'] < max_lat)
    within_long = (min_long < df['LONGITUDE']) & (df['LONGITUDE'] < max_long)
    return df[within_lat & within_long]


def df_between_years(df, y1, y2):
    """
    Filter dataframe by being between two year, y1 and y2.
    """
    return df[(y1 <= df['CRASH TIME'].dt.year) & (df['CRASH TIME'].dt.year <= y2)]


def load_from_saved():
    """
    Load from a saved version of the data file into a dataframe.
    """
    year_df_dict = {}
    for year in YEARS:
        year_df = pd.read_csv(f'year_{year}.csv')
        year_df['CRASH TIME'] = pd.to_datetime(year_df['CRASH TIME'])
        year_df_dict[year] = year_df
    cleaned_df = pd.read_csv('cleaned_analytics_data.csv')
    cleaned_df['CRASH TIME'] = pd.to_datetime(cleaned_df['CRASH TIME'])
    return cleaned_df, year_df_dict


def read_data(set_location=False, save_cleaned=False, save_years=False):
    """
    Read and clean the data for most use cases.
    Additional cleaning needed for type of collision and quantizing values.
    """
    collision_df = pd.read_csv(MOTOR_VEHICLE_COLLISIONS_CSV)
    # columns to keep
    columns = ['CRASH DATE', 'CRASH TIME', 'BOROUGH', 'LATITUDE', 'LONGITUDE', 'NUMBER OF PERSONS INJURED', 'NUMBER OF PERSONS KILLED', 'NUMBER OF PEDESTRIANS INJURED',
            'NUMBER OF PEDESTRIANS KILLED', 'NUMBER OF CYCLIST INJURED', 'NUMBER OF CYCLIST KILLED', 'NUMBER OF MOTORIST INJURED', 'NUMBER OF MOTORIST KILLED']
    collision_df = collision_df[columns].copy()

    # Combine crash date and crash time into datetime
    collision_df['CRASH TIME'] = pd.to_datetime(collision_df['CRASH DATE'] + ' ' + collision_df['CRASH TIME'], format='%m/%d/%Y %H:%M')
    del collision_df['CRASH DATE']

    # fill NaN lat and long with 0 to treat 0 and NaN the same
    collision_df.fillna({'LATITUDE': 0, 'LONGITUDE': 0}, inplace=True)
    cleaned_df = collision_df.copy()

    # filter out where borough is blank or coordinates are 0
    cleaned_df = cleaned_df[cleaned_df['BOROUGH'].notnull() | cleaned_df['LONGITUDE'] != 0]

    # clean an edge case on Queensboro Bridge having wrong longitude and no borough
    cleaned_df.loc[cleaned_df['LONGITUDE'] == -201.23706, ['BOROUGH', 'LONGITUDE']] = ['MANHATTAN', -73.95337]

    # filter out coordinates that are not in NYC
    within_lat = (MIN_LATITUDE < cleaned_df['LATITUDE']) & (cleaned_df['LATITUDE'] < MAX_LATITUDE)
    within_long = (MIN_LONGITUDE < cleaned_df['LONGITUDE']) & (cleaned_df['LONGITUDE'] < MAX_LONGITUDE)
    # these records should have borough labels and should not be thrown out as we handled that before
    no_lat_long = ((cleaned_df['LATITUDE'] == 0) & (cleaned_df['LATITUDE'] == 0))
    cleaned_df = cleaned_df[(within_lat & within_long) | no_lat_long]

    # save and output
    year_df_dict = {}
    for year in YEARS:
        year_df = df_filter_by(cleaned_df, 'year', year)
        if save_years:
            year_df.to_csv(f'year_{year}.csv')
        year_df_dict[year] = year_df
    if save_cleaned:
        cleaned_df.to_csv('cleaned_analytics_data.csv')
    return cleaned_df, year_df_dict


def query_accidents_by_value_and_year(cleaned_df, column_name, column_dict, print_step=False):
    """
    Parses dataframe and returns a dictionary indicating accidents in each month by year.
    """
    # creates a dictionary where each key maps to a list
    counts = defaultdict(list)
    for year in YEARS:
        if print_step:
            print('Showing year:', year)
        # remove rows from df that don't contain year in year column
        year_df = df_filter_by(cleaned_df, 'year', year)

        # handle possibility of column dict being a dict
        column_dict_keys = column_dict
        if isinstance(column_dict_keys, dict):
            column_dict_keys = column_dict_keys.keys()

        for column_value in column_dict_keys:
            # remove rows from df that don't contain column_value in column_name column
            column_value_df = df_filter_by(year_df, column_name, column_value)
            if print_step:
                print('   ', column_dict[column_value] if(isinstance(column_dict, dict)) else column_value, column_value_df.shape[0])
            # append number of remaining rows in month_df,
            # each index of counts[value] correlates with year
            counts[column_dict[column_value] if(isinstance(column_dict, dict)) else column_value].append(column_value_df.shape[0])

    # return dictionary of mapping of values to a list of accident counts by year
    return counts


def query_accidents_by_weekday_and_time_and_year(cleaned_df, print_step=False):
    """
    Parses dataframe and returns a dictionary indicating accidents each hour
    for each day of the week in each year.
    """
    counts = defaultdict(lambda: defaultdict(list))
    for year in YEARS:
        if print_step:
            print('Showing year:', year)
        year_df = df_filter_by(cleaned_df, 'year', year)
        for hour in HOURS:
            if print_step:
                print('   ', hour)
            # quantize times by top of the hour
            hour_df = df_filter_by(year_df, 'hour', hour)
            for day in DAYS:
                day_df = df_filter_by(hour_df, 'day', day)
                if print_step:
                    print('       ', day, day_df.shape[0])
                counts[year][day].append(day_df.shape[0])
    return counts


def query_accidents_by_borough_and_month_and_year(cleaned_df, print_step=False):
    """
    Parses dataframe and returns a dictionary indicating accidents by borough
    for each month in each year.
    """
    counts = defaultdict(lambda: defaultdict(list))
    for year in YEARS:
        if print_step:
            print('Showing year:', year)
        year_df = df_filter_by(cleaned_df, 'year', year)
        for borough in BOROUGH_COORDS.keys():
            if print_step:
                print('   ', borough)
            borough_df = df_filter_by(year_df, 'borough', borough)
            for month in MONTHS.keys():
                month_df = df_filter_by(borough_df, 'month', month)
                if print_step:
                    print('       ', MONTHS[month], month_df.shape[0])
                counts[year][borough].append(month_df.shape[0])
    return counts


def query_accidents_by_borough_and_day_and_year(cleaned_df, print_step=False):
    """
    Parses dataframe and returns a dictionary indicating accidents by borough
    for each day of the week in each year.
    """
    counts = defaultdict(lambda: defaultdict(list))
    for year in YEARS:
        if print_step:
            print('Showing year:', year)
        year_df = df_filter_by(cleaned_df, 'year', year)
        for borough in BOROUGH_COORDS.keys():
            if print_step:
                print('   ', borough)
            borough_df = df_filter_by(year_df, 'borough', borough)
            for day in DAYS:
                day_df = df_filter_by(borough_df, 'day', day)
                if print_step:
                    print('       ', day, day_df.shape[0])
                counts[year][borough].append(day_df.shape[0])
    return counts


def query_accidents_by_borough_and_hour_and_year(cleaned_df, print_step=False):
    """
    Parses dataframe and returns a dictionary indicating accidents by borough
    for each hour of the day in each year.
    """
    counts = defaultdict(lambda: defaultdict(list))
    for year in YEARS:
        if print_step:
            print('Showing year:', year)
        year_df = df_filter_by(cleaned_df, 'year', year)
        for borough in BOROUGH_COORDS.keys():
            if print_step:
                print('   ', borough)
            borough_df = df_filter_by(year_df, 'borough', borough)
            for hour in HOURS:
                # quantize times by top of the hour
                hour_df = df_filter_by(borough_df, 'hour', hour)
                if print_step:
                    print('       ', hour, hour_df.shape[0])
                counts[year][borough].append(hour_df.shape[0])
    return counts


def plot_multiple_bar_by_metric(data, metric, title='', xlabel='', ylabel='', colors=None, total_width=0.8, single_width=1, legend=True):
    """
    Dynamically generate multiple bar graph/histogram
    """
    _, ax = plt.subplots()
    # default bar and legend colors
    if colors is None:
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        colors.append(u'slateblue')
        colors.append(u'lightgreen')
    n_bars = len(data)
    bar_width = total_width / n_bars
    # legend bars
    bars = []
    for i, (_, values) in enumerate(data.items()):
        # where to reposition bar from x
        x_offset = (i - n_bars / 2) * bar_width + bar_width / 2

        # x and y position for each bar
        for x, y in enumerate(values):
            bar = ax.bar(x + x_offset, y, width=bar_width * single_width, color=colors[i % len(colors)])

        bars.append(bar[0])
    # add title, labels, legend
    if legend:
        ax.legend(bars, data.keys())
    plt.xticks(range(len(metric)), metric)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.show()


def plot_density_by_metric(df, metric, metric_name, hue, hue_order=[], title='', xlabel='', ylabel='', colors=None, legend=True):
    """
    Dynamically generate density plot
    """
    # default bar and legend colors
    if colors is None:
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        colors.append(u'slateblue')
        colors.append(u'lightgreen')
    if not hue_order:
        sns.kdeplot(data=df, x=metric_name, hue=hue, legend=legend)
    else:
        sns.kdeplot(data=df, x=metric_name, hue=hue, hue_order=hue_order, palette=colors[:len(hue_order)], legend=legend)
    # add title, labels, legend
    plt.xlim(metric[0], metric[1])
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.show()


def subplot_multiple_bar_by_metric(ax, data, metric, title='', xlabel='', ylabel='', y_max=0, y_scale=None, total_width=0.8, single_width=1, legend=True):
    """
    Dynamically generate multiple bar graph/histogram
    """
    # default bar and legend colors
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    colors.append(u'slateblue')
    colors.append(u'lightgreen')
    n_bars = len(data)
    bar_width = total_width / n_bars
    # legend bars
    bars = []
    for i, (_, values) in enumerate(data.items()):
        # where to reposition bar from x
        x_offset = (i - n_bars / 2) * bar_width + bar_width / 2

        # x and y position for each bar
        for x, y in enumerate(values):
            y_max = max(y_max, y)
            bar = ax.bar(x + x_offset, y, width=bar_width * single_width, color=colors[i % len(colors)])

        bars.append(bar[0])
    # add title, labels, legend
    if legend:
        ax.legend(bars, data.keys())
    plt.xticks(range(len(metric)), metric)
    if y_scale is not None:
        plt.yticks(np.arange(0, y_max, y_scale))
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)


def plot_basemap_scatter(cleaned_df):
    """
    Scatterplot of latitude and longitude. Does not display density of points well.
    """
    latlon = cleaned_df.loc[cleaned_df['LONGITUDE'] != 0, ['LATITUDE', 'LONGITUDE']].to_numpy()

    map = Basemap(llcrnrlon=MIN_LONGITUDE,
                  llcrnrlat=MIN_LATITUDE,
                  urcrnrlon=MAX_LONGITUDE,
                  urcrnrlat=MAX_LATITUDE,
                  ellps='WGS84',
                  resolution='f',
                  area_thresh=0.6)
    map.drawcoastlines(color='gray', zorder=2)
    map.drawcountries(color='gray', zorder=2)
    map.fillcontinents(color='#FFEEDD')
    map.drawstates(color='gray', zorder=2)
    map.drawmapboundary(fill_color='#DDEEFF')

    map.scatter(latlon[:, 1], latlon[:, 0], marker='o', c='red', zorder=3, latlon=True)
    plt.show()


def density_estimation(lon, lat):
    """
    Compute the kernel density of lat and long into a third dimension using a Gaussian
    """
    lon_values, lat_values = np.mgrid[lon.min():lon.max():100j, lat.min():lat.max():100j]
    positions = np.vstack([lon_values.ravel(), lat_values.ravel()])
    # compute the kernel from latitude and longitude values
    kernel = gaussian_kde(np.vstack([lon, lat]))
    density_values = np.reshape(kernel(positions).T, lon_values.shape)
    return lon_values, lat_values, density_values


def plot_basemap_heat_density(borough_df, borough, xprecision=3, yprecision=3, num_levels=11, cmap='Reds', colorbar=True, title=""):
    """
    Generate the heatmap density contours for the given data that has already been
    filtered to only contain the borough and only valid coordinates in that borough.
    """
    _, ax = plt.subplots()
    latlon = borough_df[['LATITUDE', 'LONGITUDE']].to_numpy()
    # longitude
    lon = latlon[:, 1]
    # latitude
    lat = latlon[:, 0]

    # perform kernel density estimation on longitude, latitude
    lon_values, lat_values, density_values = density_estimation(lon, lat)

    extent = BOROUGH_EXTENT[borough]
    llcrnrlon, urcrnrlon, llcrnrlat, urcrnrlat = extent
    # use image of borough map as background
    map = Basemap(llcrnrlon=llcrnrlon,
                  llcrnrlat=llcrnrlat,
                  urcrnrlon=urcrnrlon,
                  urcrnrlat=urcrnrlat)
    im = Image.open(f'{borough.lower()}.png')
    map.imshow(im, origin='upper', alpha=0.85, extent=extent)

    # add axis settings
    xlabels = np.around(np.linspace(llcrnrlon, urcrnrlon, xprecision), 2)
    ylabels = np.around(np.linspace(llcrnrlat, urcrnrlat, yprecision), 2)
    ax.set_xlim(llcrnrlon, urcrnrlon)
    ax.set_ylim(llcrnrlat, urcrnrlat)
    ax.set_xticks(xlabels)
    ax.set_yticks(ylabels)
    map.drawmeridians(xlabels, labels=[1,0,0,0], linewidth=0)
    map.drawparallels(ylabels, labels=[0,0,0,1], linewidth=0)

    # generate density contours
    levels = np.linspace(0, density_values.max(), num_levels)
    map.contourf(lon_values, lat_values, density_values, levels=levels, cmap=cmap,
                 alpha=0.5, extent=np.around([lon.min(), lon.max(), lat.min(), lat.max()], 3))

    # show contour bar
    if colorbar:
        map.colorbar(pad=0.5)

    plt.title(title)

    plt.show()


def visualize_one(cleaned_df):
    """
    Filter the dataframe to get the data for plotting a histogram and density plot by borough and year.
    """
    print('Question 1')
    data = query_accidents_by_value_and_year(cleaned_df, 'borough', BOROUGH_COORDS)
    plot_multiple_bar_by_metric(data, YEARS, title='Accidents by Borough from 2013 to 2020', xlabel='Year', ylabel='Accidents')
    metric = [datetime(2013, 1, 1), datetime(2021, 1, 1)]
    plot_density_by_metric(cleaned_df, metric, 'CRASH TIME', 'BOROUGH', hue_order=BOROUGH_COORDS.keys(), title='Accident Density by Borough from 2013 to 2020', xlabel='Year', ylabel='Accident Density')


def visualize_two(cleaned_df):
    """
    Filter the dataframe to get the data for plotting a histogram by month and year.
    """
    print('Question 2')
    data = query_accidents_by_value_and_year(cleaned_df, 'month', MONTHS)
    plot_multiple_bar_by_metric(data, YEARS, title='Accidents by Month from 2013 to 2020', xlabel='Year', ylabel='Accidents')


def visualize_four(cleaned_df):
    """
    Filter the dataframe to get the data for plotting a histogram by by day of the week and year.
    """
    print('Question 4')
    data = query_accidents_by_value_and_year(cleaned_df, 'day', DAYS)
    plot_multiple_bar_by_metric(data, YEARS, title='Accidents by Day of the Week from 2013 to 2020', xlabel='Year', ylabel='Accidents')


def visualize_five(cleaned_df, year_df_dict, subplot=False):
    """
    Set subplot to True for side-by-side and similarly scaled plots. Easier for comparisons.
    Otherwise plot each year individually.
    """
    print('Question 5')
    data = query_accidents_by_weekday_and_time_and_year(cleaned_df)

    if subplot:
        fig = plt.figure()
        for index, year in enumerate(YEARS[:4]):
            legend = index == 0
            ax = fig.add_subplot(2, 2, index + 1)
            subplot_multiple_bar_by_metric(ax, data[year], HOURS, title=f'Accidents by Hour each Day of the Week in {year}', xlabel='Hour', ylabel='Accidents', y_max=2800, y_scale=500, legend=legend)
        plt.show()

        fig = plt.figure()
        for index, year in enumerate(YEARS[4:]):
            legend = index == 0
            ax = fig.add_subplot(2, 2, index + 1)
            subplot_multiple_bar_by_metric(ax, data[year], HOURS, title=f'Accidents by Hour each Day of the Week in {year}', xlabel='Hour', ylabel='Accidents', y_max=2800, y_scale=500, legend=legend)
        plt.show()
    for year in YEARS:
        plot_multiple_bar_by_metric(data[year], HOURS, title=f'Accidents by Hour each Day of the Week in {year}', xlabel='Hour', ylabel='Accidents')
        year_df = year_df_dict[year]
        # make a copy to overwrite columns for visualization
        year_copy_df = year_df.copy()
        year_copy_df['DAY'] = year_copy_df['CRASH TIME'].dt.day_name()
        year_copy_df['CRASH TIME'] = year_copy_df['CRASH TIME'].dt.hour
        cat_type = CategoricalDtype(categories=DAYS, ordered=True)
        year_copy_df['DAY'] = year_copy_df['DAY'].astype(cat_type)
        metric = [0, 23]
        plot_density_by_metric(year_copy_df, metric, 'CRASH TIME', 'DAY', title=f'Accident Density by Hour each Day of the Week in {year}', xlabel='Hour', ylabel='Accident Density')


def visualize_six(cleaned_df, year_df_dict, month=True, weekday=True, hour=True, subplot=False):
    """
    Filter the dataframe to get the data for plotting histograms and density plots for each individual year
    by month, day of the week, and hour.
    Set subplot to True for side-by-side and similarly scaled plots. Easier for comparisons.
    Otherwise plot each year individually.
    """
    print('Question 6')
    if month:
        print('months')
        data = query_accidents_by_borough_and_month_and_year(cleaned_df)
        # plot 2013-2017 and 2018-2021 side by side
        if subplot:
            fig = plt.figure()
            for index, year in enumerate(YEARS[:4]):
                legend = index == 0
                ax = fig.add_subplot(2, 2, index + 1)
                subplot_multiple_bar_by_metric(ax, data[year], MONTHS.keys(), title=f'Accidents in Boroughs by Month in {year}', xlabel='Month', ylabel='Accidents', y_max=5000, y_scale=1000, legend=legend)
            plt.show()

            fig = plt.figure()
            for index, year in enumerate(YEARS[4:]):
                legend = index == 0
                ax = fig.add_subplot(2, 2, index + 1)
                subplot_multiple_bar_by_metric(ax, data[year], MONTHS.keys(), title=f'Accidents in Boroughs by Month in {year}', xlabel='Month', ylabel='Accidents', y_max=5000, y_scale=1000, legend=legend)
            plt.show()
        for year in YEARS:
            plot_multiple_bar_by_metric(data[year], MONTHS.keys(), title=f'Accidents in Boroughs by Month in {year}', xlabel='Month', ylabel='Accidents')
            metric = [datetime(year, 1, 1), datetime(year, 12, 31)]
            plot_density_by_metric(cleaned_df, metric, 'CRASH TIME', 'BOROUGH', hue_order=BOROUGH_COORDS.keys(), title=f'Accident Density by Month in {year}', xlabel='Month', ylabel='Accident Density')

    if weekday:
        print('weekdays')
        data = query_accidents_by_borough_and_day_and_year(cleaned_df)
        # plot 2013-2017 and 2018-2021 side by side
        if subplot:
            fig = plt.figure()
            for index, year in enumerate(YEARS[:4]):
                legend = index == 0
                ax = fig.add_subplot(2, 2, index + 1)
                subplot_multiple_bar_by_metric(ax, data[year], DAYS, title=f'Accidents in Boroughs by Day of the Week in {year}', xlabel='Day of the Week', ylabel='Accidents', y_max=7900, y_scale=1000, legend=legend)
            plt.show()

            fig = plt.figure()
            for index, year in enumerate(YEARS[4:]):
                legend = index == 0
                ax = fig.add_subplot(2, 2, index + 1)
                subplot_multiple_bar_by_metric(ax, data[year], DAYS, title=f'Accidents in Boroughs by Day of the Week in {year}', xlabel='Day of the Week', ylabel='Accidents', y_max=7900, y_scale=1000, legend=legend)
            plt.show()
        for year in YEARS:
            plot_multiple_bar_by_metric(data[year], DAYS, title=f'Accidents in Boroughs by Day of the Week in {year}', xlabel='Day of the Week', ylabel='Accidents')

    if hour:
        print('hours')
        data = query_accidents_by_borough_and_hour_and_year(cleaned_df)
        if subplot:
            fig = plt.figure()
            for index, year in enumerate(YEARS[:4]):
                legend = index == 0
                ax = fig.add_subplot(2, 2, index + 1)
                subplot_multiple_bar_by_metric(ax, data[year], HOURS, title=f'Accidents in Boroughs by Hour in {year}', xlabel='Hour', ylabel='Accidents', y_max=4000, y_scale=500, legend=legend)
            plt.show()

            fig = plt.figure()
            for index, year in enumerate(YEARS[4:]):
                legend = index == 0
                ax = fig.add_subplot(2, 2, index + 1)
                subplot_multiple_bar_by_metric(ax, data[year], HOURS, title=f'Accidents in Boroughs by Hour in {year}', xlabel='Hour', ylabel='Accidents', y_max=4000, y_scale=500, legend=legend)
            plt.show()
        for year in YEARS:
            plot_multiple_bar_by_metric(data[year], HOURS, title=f'Accidents in Boroughs by Hour in {year}', xlabel='Hour', ylabel='Accidents')
            year_df = year_df_dict[year]
            # make a copy to overwrite columns for visualization
            year_df = year_df.copy()
            year_df['HOUR'] = year_df['CRASH TIME'].dt.hour
            metric = [0, 23]
            plot_density_by_metric(year_df, metric, 'HOUR', 'BOROUGH', hue_order=BOROUGH_COORDS.keys(), title=f'Accident Density in Boroughs by Hour in {year}', xlabel='Hour', ylabel='Accident Density')
        # density plot by hour for each year from 2013 to 2020
        for borough in BOROUGH_COORDS.keys():
            temp_df = df_filter_by(cleaned_df, 'borough', borough)
            temp_df = temp_df.copy()
            temp_df = df_between_years(temp_df, 2013, 2020)
            temp_df['HOUR'] = temp_df['CRASH TIME'].dt.hour
            temp_df['YEAR'] = temp_df['CRASH TIME'].dt.year
            metric = [0, 23]
            plot_density_by_metric(temp_df, metric, 'HOUR', 'YEAR', hue_order=list(YEARS), title=f'Accident Density by Hour in {borough.title()} for Each Year', xlabel='Hour', ylabel='Accident Density')


def visualize_seven(year_df_dict, boroughs=BOROUGH_COORDS.keys(), selected_year=None):
    """
    Filter the dataframe to get the data for plotting a density heat map plot
    by borough for each year.
    By default plot all years in the dict and for all boroughs.
    Optionally specify a single year or list of boroughs.
    """
    # make sure the optional selected year is within acceptable range
    if selected_year is not None:
        assert selected_year > 2012 and selected_year < 2021
    for borough in boroughs:
        if selected_year is None:
            for year in year_df_dict.keys():
                # filter by year and borough
                year_df = year_df_dict[year]
                borough_df = df_filter_by(year_df, 'borough', borough)
                # make sure coordinates are in borough
                c1, c2 = BOROUGH_BOUNDS[borough]
                borough_df = df_between_coords(borough_df, c1, c2)
                title = f'Accident Density in {borough.title()} in {year}'
                plot_basemap_heat_density(borough_df, borough, title=title)
        else:
            # filter by year and borough
            year_df = year_df_dict[selected_year]
            borough_df = df_filter_by(year_df, 'borough', borough)
            # make sure coordinates are in borough
            c1, c2 = BOROUGH_BOUNDS[borough]
            borough_df = df_between_coords(borough_df, c1, c2)
            title = f'Accident Density in {borough.title()} in {selected_year}'
            plot_basemap_heat_density(borough_df, borough, title=title)

def query_accidents_by_deaths_and_month(cleaned_df, print_step=False):
    """
    retrieves the number of accident deaths by each month, also returns
    the ratio of deaths to accidents in each month
    """
    death_counts = defaultdict(list)
    death_ratio = defaultdict(list)
    for year in YEARS:
        if print_step:
            print('Showing year:', year)
        year_df = df_filter_by(cleaned_df, 'year', year)
        for month in MONTHS.keys():
            month_df = df_filter_by(year_df, 'month', month)
            deaths = month_df['NUMBER OF PERSONS KILLED'].sum()
            if print_step:
                print('   ', MONTHS[month], deaths)
            death_counts[MONTHS[month]].append(deaths)
            death_ratio[MONTHS[month]].append(deaths/month_df.shape[0])
    return YEARS, death_counts, death_ratio


def visualize_nine(cleaned_df):
    """ graphs the histograms for 9, accident deaths by month and accident death ratio by month"""
    years, data, data_with_ratio = query_accidents_by_deaths_and_month(cleaned_df, print_step=True)
    fig = plt.figure()
    plot_multiple_bar_by_metric(data, years,
                                title=f'Accidents Deaths by Month from 2013 to 2020', xlabel='Month',
                                ylabel='Deaths')
    plt.show()
    fig = plt.figure()
    plot_multiple_bar_by_metric(data_with_ratio, years,
                                title=f'Death to Accident Ratio by Month from 2013 to 2020', xlabel='Month',
                                ylabel='Death to Accident Ratio')
    plt.show()

def visualize_three():
    """
    Create a visualization for each type of accident per year.
    Accident type is classified by contributing factors and/or involved parties.
    """
    # read in cleaned data - visualization specific
    cleaned_df = pd.read_csv(CLEAN_MOTOR_VEHICLE_COLLISIONS_CSV)
    # creates a dictionary where each key maps to a list
    counts_total = defaultdict(list)
    counts_percentage= defaultdict(list)
    for year in YEARS:
        filtered_data = cleaned_df[cleaned_df['CRASH YEAR {}'.format(year)] == 1]
        total_year_count = 0
        for column in ['Drug Related Factor', 'Personal Factor', 'Environmental Cause Factor', 'Failure To Obey Traffic Factor']:
            # remove rows from df that don't contain column_value in column_name column
            column_value_df = filtered_data[filtered_data[column] == 1]

            counts_total[column].append(column_value_df.shape[0])
            total_year_count += column_value_df.shape[0]
        for column in counts_total:
            counts_percentage[column].append(counts_total[column][-1] / total_year_count)

    plot_multiple_bar_by_metric(counts_total, YEARS, title='Accident Causation Counts by Year', xlabel='Year', ylabel='Accidents')

    plot_multiple_bar_by_metric(counts_percentage, YEARS, title='Accident Causation Percentages by Year', xlabel='Year', ylabel='Accidents')

    # creates a dictionary where each key maps to a list
    counts = defaultdict(list)
    for year in YEARS:
        filtered_data = cleaned_df[cleaned_df['CRASH YEAR {}'.format(year)] == 1]
        column ='INVOLVED TYPE PEDESTRIAN'
        # remove rows from df that don't contain column_value in column_name column
        column_value_df = filtered_data[filtered_data[column] == 1]
        counts[column].append(column_value_df.shape[0])

        # remove rows from df that don't contain column_value in column_name column
        column_value_df = filtered_data[filtered_data[column] == 0]
        counts['VEHICLE ONLY'].append(column_value_df.shape[0])
    plot_multiple_bar_by_metric(counts, YEARS, title='Involved Parties by Year', xlabel='Year', ylabel='Accidents')


def visualize_eight():
    """
    Create a visualization depicting involved parties in accidents by year.
    Involved party is either vehicle only or vehicle and pedestrian
    """
    # read in cleaned data - visualization specific
    cleaned_df = pd.read_csv(CLEAN_MOTOR_VEHICLE_COLLISIONS_CSV)

    # creates a dictionary where each key maps to a list
    counts = defaultdict(list)
    for year in YEARS:
        filtered_data = cleaned_df[cleaned_df['CRASH YEAR {}'.format(year)] == 1]
        column ='INVOLVED TYPE PEDESTRIAN'
        # remove rows from df that don't contain column_value in column_name column
        column_value_df = filtered_data[filtered_data[column] == 1]
        counts[column].append(column_value_df.shape[0])

        # remove rows from df that don't contain column_value in column_name column
        column_value_df = filtered_data[filtered_data[column] == 0]
        counts['VEHICLE ONLY'].append(column_value_df.shape[0])
    plot_multiple_bar_by_metric(counts, YEARS, title='Involved Parties by Year', xlabel='Year', ylabel='Accidents')


def run_visualizations(cleaned_df, year_df_dict, subplot=False):
    """
    Run all possible visualizations.
    """
    visualize_one(cleaned_df)
    visualize_two(cleaned_df)
    visualize_three()
    visualize_four(cleaned_df)
    visualize_five(cleaned_df, year_df_dict, subplot=subplot)
    visualize_six(cleaned_df, year_df_dict, month=False, weekday=False, subplot=subplot)
    visualize_seven(year_df_dict)
    visualize_eight()
    visualize_nine(cleaned_df)


# ============================================================== #
#  SECTION: Main                                                 #
# ============================================================== #


if __name__ == '__main__':
    cleaned_df, year_df_dict = read_data()
    # cleaned_df, year_df_dict = load_from_saved()
    run_visualizations(cleaned_df, year_df_dict)
