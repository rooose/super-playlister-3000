from flask import Flask, request, render_template, redirect
from flask_cors import CORS

@app.route("/", methods=['GET'])
def home_view():
    return render_template('index.html', condition=False, error='', translation='', question='')