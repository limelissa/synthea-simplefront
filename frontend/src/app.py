import flask
from flask import Flask, render_template, flash, redirect, request, send_from_directory
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Required, Optional

import time
import os
import subprocess
import json

import zipfile
import io
import pathlib


app = Flask(__name__, static_url_path='')
app.config['SECRET_KEY'] = 'key'
Bootstrap(app)


# Synthea wtforms 
class SyntheaForm(FlaskForm):
    inputSeed = IntegerField('Seed', validators=[Optional("Not a valid integer value")])
    inputNbrPatient = IntegerField('Number of patient', validators=[DataRequired("Not a valid integer value")])
    properties = TextAreaField('Synthea Properties')
    module = SelectField('Cohort')
    
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
    delete_str = "find . -type f -not -name 'makefile' -delete"
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
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip(), flush=True)
        else : 
            break
    rc = process.poll()
    return rc

    # status = subprocess.call(cmd, shell=True)
    # if status == 0 : 
    #     flash('Generation ended successfully')
    # else :
    #     flash('There was an error during generation')

# Find generated patient json files
def findLastGenerated() :
    os.chdir("/synthea/output/fhir")
    cmd = "find . -type f -not -name 'makefile'"
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    (output, err) = p.communicate()
    return output

### Flask Routes ###

@app.route("/", methods=['GET', 'POST'])
def form():
    syntheaform = SyntheaForm()
    syntheaform.module.choices = getModules()
    os.chdir("/app/resources")
    with open('synthea.properties', 'r') as file:
        data = file.read()
        file.close()
    syntheaform.properties.data = data

    if syntheaform.validate_on_submit() and request.method == "POST":
        req = request.form

        inputSeed = req.get("inputSeed")
        inputNbrPatient = req.get("inputNbrPatient")
        module = req.get('module')
        properties = req.get('properties')

        os.chdir("/synthea/src/main/resources")
        with open('synthea.properties', 'r+') as file:
            file.truncate(0)
            file.write(properties)
            file.close()

        generateSynthea(inputSeed, inputNbrPatient, module)
        return redirect('/result')
   
    return render_template("form.html", form = syntheaform)

@app.route("/result")
def result():
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
    return render_template("result.html", text = output, files = files_content)

@app.route("/result/download", methods=['GET', 'POST'])
def get_files():
    pass

@app.route("/result/send", methods=['GET', 'POST'])
def send_to_fhir():
    pass

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
