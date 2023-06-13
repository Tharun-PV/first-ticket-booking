from flask import Flask, render_template, session, redirect, url_for, flash
from admin import admin_routes
from user import user_routes

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# Register admin and user routes
app.register_blueprint(admin_routes)
app.register_blueprint(user_routes)


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
