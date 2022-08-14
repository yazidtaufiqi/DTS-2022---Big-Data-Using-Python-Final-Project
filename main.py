import matplotlib
matplotlib.use('Agg')

from flask import Flask, render_template, request, redirect
from flask_wtf import FlaskForm
from wtforms import SubmitField, SelectField
from wtforms.validators import DataRequired
from urllib.request import urlopen
from scipy.integrate import cumulative_trapezoid
from io import BytesIO
import json
import pandas as pd
import matplotlib.pyplot as plt
import base64

def read_from_url(url : str):
    response = urlopen(url)
    return json.loads(response.read())

def mission_list():
    global mission
    data_json = read_from_url("http://api.launchdashboard.space/v2/launches/spacex")
    mission = pd.DataFrame(data_json)
    return mission['name'].to_list()

def load_data(flight_number : int):
    global data, data_events
    data_json = read_from_url(f"http://api.launchdashboard.space/v2/analysed/spacex?flight_number={flight_number}")
    data = pd.DataFrame(data_json[0]['telemetry'])
    json_events = read_from_url(f"http://api.launchdashboard.space/v2/events/spacex?flight_number={flight_number}")
    data_events = pd.DataFrame(json_events)
    data_events = data_events.dropna().sort_values('time')

def create_plot(x : list, y : list, xlabel : str, ylabel : str, events : pd.DataFrame, event_pos : str = ""):
    img = BytesIO()
    plt.style.use('dark_background')
    plt.rcParams.update({"axes.facecolor" : "#212121", "figure.facecolor" : "#212121", "savefig.facecolor" : "#212121"})
    plt.plot(x, y)
    plt.xlabel(xlabel, fontsize=14)
    plt.ylabel(ylabel, fontsize=14)
    plt.grid()
    line_pos = 0
    if event_pos != "":
        for index, event in events.iterrows():
            spacing = 0.1 if event[event_pos] - line_pos > 25 or line_pos == 0 else 25 - (event[event_pos] - line_pos)
            line_pos = event[event_pos]
            plt.axvline(event[event_pos], linestyle="--", color="red")
            plt.text(event[event_pos] + spacing, 0, event['key'], rotation=60, fontsize=12)
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    return plot_url

def plot_vel():
    y = data['velocity'].to_list()
    x = data['time'].to_list()
    xlabel = "Time [s]"
    ylabel = "Velocity [m/s]"
    return create_plot(x, y, xlabel, ylabel, data_events, 'time')

def plot_alt():
    y = data['altitude'].to_list()
    x = data['time'].to_list()
    xlabel = "Time [s]"
    ylabel = "Altitude [m]"
    return create_plot(x, y, xlabel, ylabel, data_events, 'time')

def plot_fpath():
    time = data['time'].to_list()
    velocity_x = data['velocity_x'].to_list()
    velocity_y = data['velocity_y'].to_list()
    position_x = cumulative_trapezoid(velocity_x, time)
    position_y = cumulative_trapezoid(velocity_y, time)
    position_x = [x/1000 for x in position_x]
    position_y = [x/1000 for x in position_y]
    xlabel = "Position in X [km]"
    ylabel = "Position in Z [km]"
    pos_x_events = [position_x[time.index(event['time'])] for index, event in data_events.iterrows()]
    key_events = [event['key']for index, event in data_events.iterrows()]
    events = pd.DataFrame({'pos':pos_x_events, 'key':key_events})
    return create_plot(position_x, position_y, xlabel, ylabel, events)

def plot_angle():
    y = data['angle'].to_list()
    x = data['time'].to_list()
    xlabel = "Time [s]"
    ylabel = "Angle [deg]"
    return create_plot(x, y, xlabel, ylabel, data_events, 'time')

def plot_acceleration():
    y = data['acceleration'].to_list()
    x = data['time'].to_list()
    xlabel = "Time [s]"
    ylabel = "Acceleration [m/s^2]"
    return create_plot(x, y, xlabel, ylabel, data_events, 'time')

def plot_dynpress():
    y = data['q'].to_list()
    y = [q/1000 for q in y]
    x = data['time'].to_list()
    xlabel = "Time [s]"
    ylabel = "Dynamic Pressure [kPa]"
    return create_plot(x, y, xlabel, ylabel, data_events, 'time')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'very secret key'

class MissionForm(FlaskForm):
    mission = SelectField(u'Mission', choices=mission_list(), coerce=str, validators=[DataRequired()])
    submit = SubmitField('Launch')

@app.route("/", methods=['GET', 'POST'])
def home():
    form = MissionForm(request.form)
    if form.validate_on_submit():
        flight_number = mission[mission['name'] == form.mission.data].iloc[0]['flight_number']
        return redirect("/plot/" + str(flight_number))
    return render_template("index.html", form=form)

@app.route("/plot/<flight_number>", methods=['GET', 'POST'])
def plot(flight_number):
    header = mission[mission['flight_number'] == int(flight_number)].iloc[0]['name']
    form = MissionForm(request.form, mission=header)
    load_data(flight_number)
    vel = plot_vel()
    alt = plot_alt()
    fpath = plot_fpath()
    angle = plot_angle()
    acceleration = plot_acceleration()
    dynpres = plot_dynpress()
    if form.validate_on_submit():
        flight_number = mission[mission['name'] == form.mission.data].iloc[0]['flight_number']
        return redirect("/plot/" + str(flight_number))
    return render_template("base_plot.html", form=form, data=header, vel=vel, alt=alt, fpath=fpath, angle=angle, acc=acceleration, dpres=dynpres)