import flask
from flask import Flask, render_template, flash, redirect, request, send_from_directory, url_for
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import Form, StringField, SubmitField, IntegerField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Required, Optional
from flask_socketio import SocketIO, emit, join_room, leave_room, close_room, rooms, disconnect
from threading import Lock


import time
import os
import subprocess
import json

import zipfile
import io
import pathlib


async_mode = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'key'
Bootstrap(app)

socketio = SocketIO(app, async_mode=async_mode)
thread = None
thread_lock = Lock()

results = []

# Synthea wtforms 
class SyntheaForm(FlaskForm):
    inputSeed = IntegerField('Seed', validators=[Optional("Not a valid integer value")])
    inputNbrPatient = IntegerField('Number of patient', validators=[DataRequired("Not a valid integer value")])
    properties = TextAreaField('Synthea Properties')
    module = SelectField('Cohort')

class FhirUrlForm(Form):
    url = StringField('FHIR URL', validators=[DataRequired("Missing URL")], description="FHIR URL")

# Get list of modules in /synthea/src/main/resources/modules folder
def getModules():
    modules = [('', '')]
    modules_directory = '/synthea/src/main/resources/modules'
    for file in sorted(os.listdir(modules_directory)):
        if os.path.isfile(os.path.join(modules_directory, file)):
            file = file.replace('.json', '')
            module_label = file.replace('_', ' ')
            modules.append((file, module_label))
    return modules

# Generate synthetic patients with Synthea
def generateSynthea(seed, nbrPatient, module):
    os.chdir("/synthea/output/fhir")
    # delete_str = "find . -type f -not -name 'makefile' -delete"
    delete_str = "find . -type f -delete"
    status = subprocess.call(delete_str, shell=True)

    cmd = './run_synthea'
    os.chdir("/synthea")
    if seed != "" : 
        cmd = cmd + " -s " + str(seed)
    if nbrPatient != "" :
        cmd = cmd + " -p " +  str(nbrPatient)
    if module != "" :
        cmd = cmd + " -m " +  module + "*"
    print(cmd, flush=True)

    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    flag_save = False
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            line = output.strip().decode('UTF-8')
            
            if flag_save : 
                results.append(line)
            if line == 'Running with options:' :
                flag_save = True
                results.clear()
            if line.startswith('Records:') :
                flag_save = False

            print(line, flush=True)
            socketio.sleep(0.01)
            socketio.emit('my_response', {'data': line}, namespace='/test')
        else : 
            break
    rc = process.poll()
    return rc

# Find generated patient json files
def findLastGenerated() :
    os.chdir("/synthea/output/fhir")
    cmd = "find . -type f -not -name 'makefile'"
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    (output, err) = p.communicate()
    return output

#######################
### SocketIO Events ###
#######################

@socketio.on('generate', namespace='/test')
def generate(message):
    print("GENERATE", flush=True) 
    os.chdir("/synthea/src/main/resources")
    with open('synthea.properties', 'r+') as file:
        file.truncate(0)
        file.write(message['properties'])
        file.close()
    generateSynthea(message['seed'], message['nbrPatient'], message['module'])
    print('END GENERATE SYNTHEA', flush=True)
    print('url_for :',url_for('result'), flush=True)
    emit('redirect', {'url': url_for('result')})

####################
### Flask Routes ###
####################

@app.route("/", methods=['GET', 'POST'])
def form():
    syntheaform = SyntheaForm()
    syntheaform.module.choices = getModules()
    os.chdir("/app/resources")
    with open('synthea.properties', 'r') as file:
        data = file.read()
        file.close()
    syntheaform.properties.data = data

    # if syntheaform.validate_on_submit() and request.method == "POST":
    #     req = request.form

    #     inputSeed = req.get("inputSeed")
    #     inputNbrPatient = req.get("inputNbrPatient")
    #     module = req.get('module')
    #     properties = req.get('properties')

    #     os.chdir("/synthea/src/main/resources")
    #     with open('synthea.properties', 'r+') as file:
    #         file.truncate(0)
    #         file.write(properties)
    #         file.close()

    #     generateSynthea(inputSeed, inputNbrPatient, module)
    #     return redirect('/result')
   
    return render_template("form.html", form = syntheaform)

@app.route("/result", methods=['GET', 'POST'])
def result():
    print(results, flush='True')
    urlForm = FhirUrlForm(request.form)
    output = findLastGenerated()
    files = output.decode().split("\n")
    files.pop()
    files_content = []
    os.chdir("/synthea/output/fhir")
    for file in files:
        with open(file, 'r') as openfile:
            content = json.load(openfile)
            content = json.dumps(content, indent = 4)
            data = []
            data.append(file)
            data.append(content)
            files_content.append(data)

    if urlForm.validate() and request.method == 'POST':
        req = request.form
        url = req.get("url")
        os.environ["FHIR_URL"] = url
        os.chdir("/synthea/output/fhir")
        print(os.environ["FHIR_URL"], flush=True)

        process = subprocess.run(['make'], stdout=subprocess.PIPE, universal_newlines=True)

    return render_template("result.html", text = output, files = files_content, form = urlForm, log = results)


@app.route("/result/send", methods=['GET', 'POST'])
def send_to_fhir():
    return 'OK'

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", debug=True)
