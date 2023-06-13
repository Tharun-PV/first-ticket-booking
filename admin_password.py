import bcrypt
from pymongo import MongoClient

client = MongoClient(
    "mongodb+srv://rolyxtharun:movie@cluster0.kvbukoj.mongodb.net/?retryWrites=true&w=majority")
db = client["flight_booking"]


def update_admin_password():
    # Prompt for existing admin email and password
    email = input("Enter existing admin email: ")
    password = input("Enter existing admin password: ")

    # Generate a hashed password for the new password
    new_password = input("Enter new admin password: ")
    hashed_password = bcrypt.hashpw(
        new_password.encode('utf-8'), bcrypt.gensalt())

    # Verify the existing admin credentials
    admin_collection = db['admin_users']
    admin_user = admin_collection.find_one({'email': email})

    if admin_user and bcrypt.checkpw(password.encode('utf-8'), admin_user['password'].encode('utf-8')):
        # Update the existing admin user's password
        admin_user['password'] = hashed_password.decode('utf-8')
        admin_collection.update_one({'_id': admin_user['_id']}, {
                                    '$set': {'password': admin_user['password']}})
        print('Admin password updated')
    else:
        print('Invalid admin credentials')


def add_new_admin():
    # Prompt for new admin email and password
    email = input("Enter new admin email: ")
    password = input("Enter new admin password: ")

    # Generate a hashed password for the new admin
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Check if the admin user already exists
    admin_collection = db['admin_users']
    existing_admin = admin_collection.find_one({'email': email})

    if existing_admin:
        print('Admin user with the provided email already exists')
    else:
        # Insert new admin user
        admin_user = {
            'email': email,
            'password': hashed_password.decode('utf-8')
        }
        admin_collection.insert_one(admin_user)
        print('New admin user inserted')


def main():
    choice = input(
        "Choose an option:\n1. Update existing admin\n2. Add new admin\n")

    if choice == '1':
        update_admin_password()
    elif choice == '2':
        add_new_admin()
    else:
        print('Invalid choice')


if __name__ == '__main__':
    main()
