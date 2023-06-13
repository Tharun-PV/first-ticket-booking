from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from functools import wraps
from pymongo import MongoClient
import bcrypt
from bson import ObjectId

user_routes = Blueprint('user_routes', __name__)

# Connect to MongoDB Atlas
client = MongoClient("mongodb+srv://rolyxtharun:movie@cluster0.kvbukoj.mongodb.net/?retryWrites=true&w=majority")
db = client["flight_booking"]

# Ticket ID generator
def get_ticket_id():
    last_ticket = db.tickets.find().sort('ticket_id', -1).limit(1)
    if db.tickets.count_documents({}) == 0:
        ticket_id = '#FT01'
    else:
        last_ticket_id = last_ticket[0]['ticket_id']
        numeric_part = int(last_ticket_id[3:])
        new_numeric_part = numeric_part + 1
        ticket_id = '#FT' + str(new_numeric_part).zfill(2)
    db.tickets.insert_one({'ticket_id': ticket_id})
    return ticket_id


#user session email to name
@user_routes.context_processor
def utility_processor():
    def get_user_name(email):
        user_data = db.users.find_one({'email': email})
        if user_data:
            return user_data['name']
        else:
            return 'Unknown User'
    return dict(get_user_name=get_user_name)

# User login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('user_routes.user_login'))
        return f(*args, **kwargs)
    return decorated_function


#user signup
@user_routes.route('/user_signup', methods=['GET', 'POST'])
def user_signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        hashed_password = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt())

        user_ref = db['users'].find_one({'email': email})
        if user_ref:
            return render_template('user_signup.html', error='User with this email already exists')

        user_data = {
            'name': name,
            'email': email,
            'password': hashed_password.decode('utf-8')
        }
        db['users'].insert_one(user_data)

        return redirect(url_for('user_routes.user_login'))

    return render_template('user_signup.html')



#user login
@user_routes.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if session.get('logged_in'):
        return redirect(url_for('user_routes.user_dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = db['users'].find_one({'email': email})

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            session['email'] = email
            session['logged_in'] = True
            return redirect(url_for('user_routes.user_dashboard'))
        else:
            return render_template('user_login.html', error="Invalid email or password")

    else:
        return render_template('user_login.html')


#user dashboard
@user_routes.route('/user_dashboard')
@login_required
def user_dashboard():
    email = session.get('email')
    return render_template('user_dashboard.html', email=email)



#user search flights
@user_routes.route('/user_search_flights', methods=['GET', 'POST'])
def user_search_flights():
    if request.method == 'POST':
        airlines = request.form.get('airlines')
        departure = request.form.get('departure')
        arrival = request.form.get('arrival')
        departure_date = request.form.get('departure_date')
        departure_time = request.form.get('departure_time')
        arrival_date = request.form.get('arrival_date')
        arrival_time = request.form.get('arrival_time')

        if not any([departure, arrival, airlines]):
            flash(
                'Please enter either departure and arrival locations or select an airline')
            return redirect(url_for('user_routes.user_search_flights'))

        query = {}

        if airlines:
            query['airlines'] = airlines
        if departure:
            query['departure'] = departure
        if arrival:
            query['arrival'] = arrival
        if departure_date:
            query['departure_date'] = departure_date
        if departure_time:
            query['departure_time'] = departure_time
        if arrival_date:
            query['arrival_date'] = arrival_date
        if arrival_time:
            query['arrival_time'] = arrival_time

        flights = db.flights.find(query).limit(10)
        flight_data = list(flights)
        if not flight_data:
            flash('No flights found')
            return render_template('user_dashboard.html')

        return render_template('user_dashboard.html', flight_data=flight_data)
    else:
        return render_template('user_dashboard.html')



#user booking flights
@user_routes.route('/user_book_flight', methods=['POST'])
@login_required
def user_book_flight():
    flight_number = request.form.get('flight_number')
    user_email = session.get('email')
    existing_flight = db.flights.find_one({'flight_number': flight_number})
    if not existing_flight:
        flash('Invalid flight selection.')
        return redirect(url_for('user_routes.user_dashboard'))
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        flash('Invalid user email.')
        return redirect(url_for('user_routes.user_dashboard'))
    seats = int(request.form.get('seats', 0))
    if seats <= 0:
        flash('Invalid number of seats.')
        return redirect(url_for('user_routes.user_dashboard'))
    seat_capacity = existing_flight.get('seat_capacity', 0)
    booked_tickets = db.bookings.count_documents({'flight_number': flight_number})
    remaining_capacity = seat_capacity - booked_tickets
    if seats > remaining_capacity:
        flash('Not enough available seats.')
        return redirect(url_for('user_routes.user_dashboard'))
    ticket_ids = []
    for _ in range(seats):
        ticket_id = get_ticket_id()
        booking_data = {
            'ticket_id': ticket_id,
            'flight_number': flight_number,
            'user_id': user_data['_id']
        }
        db.bookings.insert_one(booking_data)
        ticket_ids.append(ticket_id)
    db.flights.update_one({'flight_number': flight_number}, {'$inc': {'booked_seats': seats}})
    flash(f'Booking successful. Ticket IDs: {", ".join(ticket_ids)}')
    return redirect(url_for('user_routes.user_dashboard'))


#user flight bookings
@user_routes.route('/user_bookings', methods=['GET'])
@login_required
def user_bookings():
    email = session.get('email')
    if not email:
        return redirect(url_for('user_routes.user_login'))
    user_data = db.users.find_one({'email': email})
    if not user_data:
        return redirect(url_for('user_routes.user_login'))
    bookings = db.bookings.aggregate([
        {"$match": {"user_id": user_data['_id']}},
        {"$lookup": {
            "from": "flights",
            "localField": "flight_number",
            "foreignField": "flight_number",
            "as": "flight_info"
        }},
        {"$project": {
            "_id": 0,
            "ticket_id": 1,
            "name": user_data['name'],
            "email": user_data['email'],
            "flight_info": {"$arrayElemAt": ["$flight_info", 0]}
        }}
    ])
    booking_data = []
    for booking in bookings:
        if booking.get('flight_info'):
            flight_info = booking['flight_info']
            booking_data.append({
                'ticket_id': booking['ticket_id'],
                'flight_number': flight_info['flight_number'],
                'airlines': flight_info['airlines'],
                'departure': flight_info['departure'],
                'arrival': flight_info['arrival'],
                'departure_date': flight_info['departure_date'],
                'departure_time': flight_info['departure_time'],
                'arrival_date': flight_info['arrival_date'],
                'arrival_time': flight_info['arrival_time']
            })
        else:
            booking_data.append({
                'ticket_id': booking['ticket_id'],
                'flight_number': '',
                'airlines': '',
                'departure': '',
                'arrival': '',
                'departure_date': '',
                'departure_time': '',
                'arrival_date': '',
                'arrival_time': ''
            })
    return render_template('user_bookings.html', bookings=booking_data)

#delete cancelling tickets
@user_routes.route('/user_cancel_booking', methods=['POST'])
@login_required
def user_cancel_booking():
    ticket_id = request.form['ticket_id']
    booking = db.bookings.find_one({'ticket_id': ticket_id})
    if booking:
        flight_number = booking['flight_number']
        db.bookings.delete_one({'ticket_id': ticket_id})
        db.tickets.delete_one({'ticket_id': ticket_id})
        db.flights.update_one({'flight_number': flight_number}, {'$inc': {'booked_seats': -1}})
        flash('Booking deleted successfully')
    else:
        flash('Invalid booking')
    return redirect(url_for('user_routes.user_bookings'))


#user logout
@user_routes.route('/user_logout')
def user_logout():
    session.pop('logged_in', None)
    return redirect(url_for('user_routes.user_login'))
