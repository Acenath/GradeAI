from flask_login import UserMixin
from helpers import *
class User(UserMixin):
    def __init__(self, user_id, email, _, first_name, last_name):
        self.user_id = user_id
        self.email = email
        self.first_name = first_name
        self.last_name = last_name

    @staticmethod
    def get(cursor, user_id):
        cursor.execute(''' SELECT * FROM Users WHERE user_id = %s ''', (user_id, ))
        user_id_tuple = cursor.fetchall()
        cursor.close()
        user_data = user_id_tuple[0]
        if not user_data:
            return None
        
        return User(
            user_id = user_data[0],
            email = user_data[1],
            _ = None,  
            first_name = user_data[3],
            last_name = user_data[4]
        )
        
    
    def is_authenticated(self, cursor):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return self.user_id
    