from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/book')
def book():
    return render_template('book.html')

@app.route('/pay')
def pay():
    return render_template('pay.html')

@app.route('/login')
def login():
    return render_template('login.html')
