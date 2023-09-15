from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
from functools import wraps
from pymongo import MongoClient
import bcrypt
from bson import ObjectId
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import random
import time
from datetime import datetime

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
        user_ref = db['users'].find_one({'email': email})
        if user_ref:
            return render_template('user_signup.html', error='User with this email already exists')
        session['name'] = name
        session['email'] = email
        session['password'] = password
        otp = random.randint(100000, 999999)
        session['otp'] = {'code': otp, 'timestamp': time.time()}
        subject = 'Flight Ticket - OTP Verification'
        message = '''
Dear {},
Thank you for signing up for our service. To verify your account, please enter the following One-Time Password (OTP) within 60 seconds:
OTP: {}
If you did not initiate this request or have any concerns, please disregard this email.
Thank you for choosing our service.
        
Best regards,
[Flight Booking Team]
        '''.format(name, otp)
        sender_email = current_app.config['OUTLOOK_EMAIL']
        sender_password = current_app.config['OUTLOOK_PASSWORD']
        recipient_email = email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'plain'))
        try:
            server = smtplib.SMTP('smtp.office365.com', 587)
            server.ehlo()
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
            server.close()
            print(name, email, password, otp)
            return redirect(url_for('user_routes.user_otp'))
        except Exception as e:
            return render_template('user_signup.html', error='Failed to send OTP. Please try again.')
    return render_template('user_signup.html')

#user otp
@user_routes.route('/user_otp', methods=['GET', 'POST'])
def user_otp():
    if request.method == 'POST':
        user_otp = int(request.form['otp'])
        stored_otp = session.get('otp')
        timestamp = stored_otp.get('timestamp') if stored_otp else None
        print('user_otp:', user_otp)
        print('stored_otp:', stored_otp)
        print('timestamp:', timestamp)
        if isinstance(stored_otp, dict) and user_otp == stored_otp.get('code'):
            current_time = time.time()
            time_difference = current_time - timestamp
            print('current_time:', current_time)
            print('time_difference:', time_difference)

            if time_difference <= 60:
                name = session.get('name')
                email = session.get('email')
                password = session.get('password')
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                user_data = {
                    'name': name,
                    'email': email,
                    'password': hashed_password.decode('utf-8')
                }
                db['users'].insert_one(user_data)
                session.pop('name', None)
                # session.pop('email', None)
                session.pop('password', None)
                session.pop('otp', None)
                session['logged_in'] = True
                return redirect(url_for('user_routes.user_dashboard'))
            else:
                return render_template('user_otp.html', error='OTP has expired. Please request a new OTP.')
        else:
            return render_template('user_otp.html', error='Invalid OTP. Please try again.')
    elif request.method == 'GET':
        if 'resend_otp' in request.args:
            stored_otp = session.get('otp')
            if stored_otp:
                otp = stored_otp.get('code')
                email = session.get('email')
                subject = 'Flight Ticket - OTP Resend'
                message = '''
Dear User,
You requested to resend the OTP for your account verification. Here is your new OTP:
OTP: {}

If you did not initiate this request or have any concerns, please disregard this email.

Best regards,
[Flight Booking Team]
                '''.format(otp)
                sender_email = current_app.config['OUTLOOK_EMAIL']
                sender_password = current_app.config['OUTLOOK_PASSWORD']
                recipient_email = email
                msg = MIMEMultipart()
                msg['From'] = sender_email
                msg['To'] = recipient_email
                msg['Subject'] = subject
                msg.attach(MIMEText(message, 'plain'))
                try:
                    server = smtplib.SMTP('smtp.office365.com', 587)
                    server.ehlo()
                    server.starttls()
                    server.login(sender_email, sender_password)
                    server.sendmail(sender_email, recipient_email, msg.as_string())
                    server.close()
                    return redirect(url_for('user_routes.user_otp'))
                except Exception as e:
                    flash('Failed to resend OTP. Please try again.')
                    return redirect(url_for('user_routes.user_otp'))
        else:
            stored_otp = session.get('otp')
            if stored_otp:
                return render_template('user_otp.html')
            else:
                return redirect(url_for('user_routes.user_signup'))
    return render_template('user_otp.html')

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
            flash('Please enter either departure and arrival locations or select an airline')
            return redirect(url_for('user_routes.user_search_flights'))
        # Check if departure date and time are in the future
        current_datetime = datetime.now()
        if departure_date and departure_time:
            departure_datetime = datetime.strptime(departure_date + ' ' + departure_time, '%Y-%m-%d %H:%M')
            if departure_datetime < current_datetime:
                flash('Departure date and time cannot be in the past')
                return redirect(url_for('user_routes.user_search_flights'))
        # Check if arrival date and time are after departure date and time
        if departure_date and departure_time and arrival_date and arrival_time:
            departure_datetime = datetime.strptime(departure_date + ' ' + departure_time, '%Y-%m-%d %H:%M')
            arrival_datetime = datetime.strptime(arrival_date + ' ' + arrival_time, '%Y-%m-%d %H:%M')
            if arrival_datetime <= departure_datetime:
                flash('Arrival date and time should be after departure date and time')
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
    
# user passengers details
@user_routes.route('/user_passenger', methods=['GET', 'POST'])
def user_passenger():
    if request.method == 'POST':
        flight_number = request.form['flight_number']
        seats = request.form['seats']
        session['flight_number'] = flight_number
        session['seats'] = seats
        num_tickets = int(request.form['seats'])
        return redirect(url_for('user_routes.user_passenger_details', num_tickets=num_tickets))
    return render_template('user_dashboard.html')

# user passenger details
@user_routes.route('/user_passenger_details/<int:num_tickets>', methods=['GET', 'POST'])
def user_passenger_details(num_tickets):
    if request.method == 'POST':
        passengers = []
        email = session.get('email')
        flight_number = session.get('flight_number')
        for i in range(1, num_tickets + 1):
            name = request.form.get(f'name_{i}')
            age = request.form.get(f'age_{i}')
            gender = request.form.get(f'gender_{i}')
            if name and age and gender:
                passenger = {'name': name, 'age': age, 'gender': gender, 'email': email, 'flight_number': flight_number}
                passengers.append(passenger)
            else:
                flash('Please fill in all passenger details.')
                return redirect(url_for('user_routes.user_passenger_details', num_tickets=num_tickets))
        if passengers:
            passengers_collection = db['passengers']
            passengers_collection.insert_many(passengers)
        return redirect(url_for('user_routes.user_payment', num_tickets=num_tickets))
    return render_template('user_passenger.html', num_tickets=num_tickets)

# Route for the payment page
@user_routes.route('/user_payment/<int:num_tickets>', methods=['GET', 'POST'])
def user_payment(num_tickets):
    if request.method == 'POST':
        return redirect(url_for('user_routes.user_book_flight', num_tickets=num_tickets))
    total_amount = num_tickets * 10000
    return render_template('user_payment.html', num_tickets=num_tickets, total_amount=total_amount)

#user booking flights
@user_routes.route('/user_book_flight', methods=['POST'])
@login_required
def user_book_flight():
    flight_number = session.pop('flight_number', None)
    user_email = session.get('email')
    existing_flight = db.flights.find_one({'flight_number': flight_number})
    if not existing_flight:
        flash('Invalid flight selection.')
        return redirect(url_for('user_routes.user_dashboard'))
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        flash('Invalid user email.')
        return redirect(url_for('user_routes.user_dashboard'))
    seats = int(session.get('seats', 0))
    if seats <= 0:
        flash('Invalid number of seats.')
        return redirect(url_for('user_routes.user_dashboard'))
    seat_capacity = existing_flight.get('seat_capacity', 0)
    booked_seats = existing_flight.get('booked_seats', 0)
    remaining_capacity = seat_capacity - booked_seats
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
    subject = 'Flight Booking - Booking Confirmation'
    message = f'''
Dear {user_data['name']},

Thank you for booking your flight with us. Your booking is confirmed.

Flight Details:
Flight Number: {flight_number}
Seat No.: {", ".join(ticket_ids)}

We hope you have a pleasant journey!

Best regards,
[Flight Booking Team]
    '''
    sender_email = current_app.config['OUTLOOK_EMAIL']
    sender_password = current_app.config['OUTLOOK_PASSWORD']
    recipient_email = user_email
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))
    try:
        server = smtplib.SMTP('smtp.office365.com', 587)
        server.ehlo()
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.close()
        flash(f'Booking successful. Seat No.: {", ".join(ticket_ids)}')
        return redirect(url_for('user_routes.user_dashboard'))
    except Exception as e:
        flash('Failed to send booking acknowledgment email. Please check your email settings.')
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
        user_email = session.get('email')
        db.bookings.delete_one({'ticket_id': ticket_id})
        db.tickets.delete_one({'ticket_id': ticket_id})
        db.flights.update_one({'flight_number': flight_number}, {'$inc': {'booked_seats': -1}})
        flash('Booking deleted successfully')
        subject = 'Flight Booking - Booking Cancellation'
        message = f'''
Dear User,
        
Your booking with Seat No. {ticket_id} has been successfully canceled.
        
We hope to serve you again in the future.
        
Best regards,
Flight Booking Team
        '''
        sender_email = current_app.config['OUTLOOK_EMAIL']
        sender_password = current_app.config['OUTLOOK_PASSWORD']
        recipient_email = user_email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'plain'))
        try:
            server = smtplib.SMTP('smtp.office365.com', 587)
            server.ehlo()
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
            server.close()
            return redirect(url_for('user_routes.user_bookings'))
        except Exception as e:
            flash('Failed to send cancellation confirmation email. Please check your email settings.')
            return redirect(url_for('user_routes.user_bookings'))
    else:
        flash('Invalid booking')
        return redirect(url_for('user_routes.user_bookings'))

#user logout
@user_routes.route('/user_logout')
def user_logout():
    session.pop('logged_in', None)
    session.pop('email', None)
    return redirect(url_for('user_routes.user_login'))
