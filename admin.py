from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
from functools import wraps
from pymongo import MongoClient
import bcrypt
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

admin_routes = Blueprint('admin_routes', __name__)

# Connect to MongoDB Atlas
client = MongoClient("mongodb+srv://rolyxtharun:movie@cluster0.kvbukoj.mongodb.net/?retryWrites=true&w=majority")
db = client["flight_booking"]

#admin login decorator
def adminlogin_required(f):
    @wraps(f)
    def admindecorated_function(*args, **kwargs):
        if not session.get('admin_email'):
            return render_template('admin_login.html')
        return f(*args, **kwargs)
    return admindecorated_function

# admin login
@admin_routes.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_email'):
        return redirect(url_for('admin_routes.admin_dashboard'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        admin_user = db['admin_users'].find_one({'email': email})

        if admin_user and bcrypt.checkpw(password.encode('utf-8'), admin_user['password'].encode('utf-8')):
            session['admin_email'] = email
            return redirect(url_for('admin_routes.admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid email or password")
    return render_template('admin_login.html')

#admin dashboard
@admin_routes.route('/admin_dashboard', methods=['GET'])
@adminlogin_required
def admin_dashboard():
    flights = list(db.flights.find())
    bookings = list(db.bookings.aggregate([
                {"$lookup": {
            "from": "flights",
            "localField": "flight_number",
            "foreignField": "flight_number",
            "as": "flight_info"
        }},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user_info"
        }},
        {"$unwind": "$flight_info"},
        {"$unwind": "$user_info"},
        {"$project": {
            "_id": 0,
            "ticket_id": 1,
            "name": "$user_info.name",
            "email": "$user_info.email",
            "flight_number": 1,
            "airlines": "$flight_info.airlines",
            "departure": "$flight_info.departure",
            "arrival": "$flight_info.arrival",
            "departure_date": "$flight_info.departure_date",
            "departure_time": "$flight_info.departure_time",
            "arrival_date": "$flight_info.arrival_date",
            "arrival_time": "$flight_info.arrival_time"
        }}

    ]))
    for flight in flights:
        flight_number = flight['flight_number']
        seat_capacity = flight.get('seat_capacity', 0)
        booked_tickets = len([booking for booking in bookings if booking['flight_number'] == flight_number])
        remaining_capacity = seat_capacity - booked_tickets
        flight['remaining_capacity'] = remaining_capacity
    return render_template('admin_dashboard.html', flights=flights, bookings=bookings)

#admin create flight
@admin_routes.route('/admin_flight_create', methods=['POST'])
def admin_flight_create():
    airlines = request.form.get('airlines')
    aircraft = request.form.get('aircraft')
    flight_number = request.form.get('flight_number')
    departure = request.form.get('departure')
    arrival = request.form.get('arrival')
    departure_date = request.form.get('departure_date')
    departure_time = request.form.get('departure_time')
    arrival_date = request.form.get('arrival_date')
    arrival_time = request.form.get('arrival_time')
    try:
        departure_datetime = datetime.strptime(departure_date + ' ' + departure_time, '%Y-%m-%d %H:%M')
        arrival_datetime = datetime.strptime(arrival_date + ' ' + arrival_time, '%Y-%m-%d %H:%M')
    except ValueError:
        flash('Invalid date or time format')
        return redirect(url_for('admin_routes.admin_dashboard'))
    current_datetime = datetime.now()
    if departure_datetime < current_datetime:
        flash('Departure date and time cannot be in the past')
        return redirect(url_for('admin_routes.admin_dashboard'))
    if arrival_datetime <= departure_datetime:
        flash('Arrival date and time should be after departure date and time')
        return redirect(url_for('admin_routes.admin_dashboard'))
    if aircraft == 'Airbus A380':
        seat_capacity = 100
    elif aircraft == 'Airbus A300':
        seat_capacity = 85
    elif aircraft == 'Airbus A220':
        seat_capacity = 60
    else:
        flash('Invalid aircraft type')
        return redirect(url_for('admin_routes.admin_dashboard'))
    flight_data = {
        'airlines': airlines,
        'aircraft': aircraft,
        'flight_number': flight_number,
        'departure': departure,
        'arrival': arrival,
        'departure_date': departure_date,
        'departure_time': departure_time,
        'arrival_date': arrival_date,
        'arrival_time': arrival_time,
        'seat_capacity': seat_capacity,
        'booked_seats': 0
    }
    try:
        db.flights.insert_one(flight_data)
        flash('Flight created successfully.')
    except Exception as e:
        flash('Error occurred while creating the flight.')

    return redirect(url_for('admin_routes.admin_dashboard'))

#admin flight cancelling
@admin_routes.route('/admin_flight_cancel', methods=['POST'])
def admin_flight_cancel():
    flight_number = request.form['flight_number']
    try:
        bookings = db.bookings.find({'flight_number': flight_number})
        user_emails = []
        ticket_ids = []
        for booking in bookings:
            user_id = booking['user_id']
            user_data = db.users.find_one({'_id': user_id})
            if user_data:
                user_emails.append(user_data['email'])
            ticket_ids.append(booking['ticket_id'])
        if user_emails:
            sender_email = current_app.config['OUTLOOK_EMAIL']
            sender_password = current_app.config['OUTLOOK_PASSWORD']
            subject = 'Flight Cancellation'
            message = '''
            Dear User,
            We regret to inform you that the flight with flight number {} has been canceled.
            Please contact customer support for further assistance.

            We apologize for any inconvenience caused.

            Best regards,
            [Flight Booking Team]
            '''.format(flight_number)
            for email in user_emails:
                msg = MIMEMultipart()
                msg['From'] = sender_email
                msg['To'] = email
                msg['Subject'] = subject
                msg.attach(MIMEText(message, 'plain'))
                try:
                    server = smtplib.SMTP('smtp.office365.com', 587)
                    server.ehlo()
                    server.starttls()
                    server.login(sender_email, sender_password)
                    server.sendmail(sender_email, email, msg.as_string())
                    server.close()
                except Exception as e:
                    flash('Error occurred while sending cancellation email to users.')
                    return redirect(url_for('admin_routes.admin_dashboard'))
        db.flights.delete_one({'flight_number': flight_number})
        if ticket_ids:
            db.tickets.delete_many({'ticket_id': {'$in': ticket_ids}})
            db.bookings.delete_many({'flight_number': flight_number})
            flash('Flight, bookings, and associated tickets deleted successfully.')
        else:
            flash('No associated bookings and tickets found.')
        return redirect(url_for('admin_routes.admin_dashboard'))
    except Exception as e:
        flash('Error occurred while canceling the flight, bookings, and tickets.')
        return redirect(url_for('admin_routes.admin_dashboard'))

#admin delete booking
@admin_routes.route('/admin_ticket_cancel', methods=['POST'])
def admin_ticket_cancel():
    ticket_id = request.form['ticket_id']
    booking = db.bookings.find_one({'ticket_id': ticket_id})
    if booking:
        user_id = booking['user_id']
        user_data = db.users.find_one({'_id': user_id})
        user_email = user_data['email']
        flight_number = booking['flight_number']
        flight_data = db.flights.find_one({'flight_number': flight_number})
        if flight_data:
            booked_seats = flight_data['booked_seats']
            new_booked_seats = booked_seats - 1
            db.bookings.delete_one({'ticket_id': ticket_id})
            db.tickets.delete_one({'ticket_id': ticket_id})
            db.flights.update_one({'flight_number': flight_number}, {'$set': {'booked_seats': new_booked_seats}})
            flash('Ticket deleted successfully')
            subject = 'Flight Ticket Cancellation'
            message = f'''
            Dear User,
            
            This is to inform you that as per your request your Seat No. {ticket_id} has been cancelled successfully.
            If you have any questions or need further assistance, please contact our customer support.
            
            Best regards,
            Flight Booking Team
            '''
            sender_email = current_app.config['OUTLOOK_EMAIL']
            sender_password = current_app.config['OUTLOOK_PASSWORD']
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = user_email
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain'))
            try:
                server = smtplib.SMTP('smtp.office365.com', 587)
                server.ehlo()
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, user_email, msg.as_string())
                server.close()
                flash('Cancellation email sent successfully')
            except Exception as e:
                flash('Failed to send cancellation email. Please check your email settings.')
        else:
            flash('Invalid flight number')
    else:
        flash('Invalid ticket ID')
    
    return redirect(url_for('admin_routes.admin_dashboard'))

#admin logout
@admin_routes.route('/admin_logout', methods=['GET'])
def admin_logout():
    session.pop('admin_email', None)
    return render_template('admin_login.html')