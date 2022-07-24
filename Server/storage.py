import sqlite3 as sql
import os
import system_security as security
from werkzeug.security import check_password_hash
import random

"""
    Storage module is used to store anything relating
    storing files on the system.

    Author: Jake James-Robinson
"""


class Database:
    """
        This is used to manage the connection
        between the database, this also ensures
        that the data is stored correctly.
    """

    @property
    def con(self):
        """
            Allows the user to have access to
            the database whilst ensuring the
            program cannot write to the class.
        """
        
        return self._db

    def save(self):
        """
            This saves any changes to the database,
            which could be handy to save the amount
            of characters required to save the database.
        """

        self._db.commit()

    def valid_login(self, keycard=""):
        con = self._db
        details = []
        valid = False
        
        for row in con.execute("SELECT ID, account_id FROM keycards"):
            keycard_result = check_password_hash(row[0], keycard)
            if keycard_result:
                for account in con.execute("SELECT first_name, last_name, permission_level, ID FROM managers WHERE ID=?", (str(row[1]))):
                    if account[2] >= 1:
                        valid = True
                        details.append(account[0])
                        details.append(account[1])
                        details.append(account[2])
                        details.append(account[3])
                
        return valid, details
    
    def __del__(self):
        try:
            # Closes the Database if it is still open.
            self._db.close() 
        # Ensures that the program does not crash if the database does not exist.
        except AttributeError:
            pass

    def _setup(self):
        con = self._db
        
        con.execute('''
            CREATE TABLE IF NOT EXISTS managers(
                ID INT PRIMARY KEY NOT NULL,
                first_name CHAR(20) NOT NULL,
                last_name CHAR(30) NOT NULL,
                permission_level INT DEFAULT 1 NOT NULL
            )
        ''')
        
        con.execute('''
            CREATE TABLE IF NOT EXISTS keycards(
                ID INT PRIMARY KEY NOT NULL,
                account_id INT NOT NULL
            )
        ''')

        con.execute('''
            CREATE TABLE IF NOT EXISTS environment_record(
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                occured_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        con.execute('''
            DROP TABLE security_sensors
        ''')

        con.execute('''
            CREATE TABLE IF NOT EXISTS security_sensors(
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname CHAR(20) NOT NULL,
                registered_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        con.execute('''
            CREATE TABLE IF NOT EXISTS security_record(
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                status INT(1) DEFAULT 1,
                security_sensor INTEGER NOT NULL,
                occured_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY 
                    (security_sensor) 
                REFERENCES 
                    security_sensors(ID)
            )
        ''')
        
        con.execute('''
            INSERT INTO managers(
                ID, first_name, last_name, permission_level
            )
            VALUES(?, ?, ?, ?)
        ''', (1, "Jake", "James-Robinson", 10))

        con.execute('''
            INSERT INTO keycards(
                ID, account_id
            )
            VALUES(?, ?)
        ''', (security.hash_password("0000000000"), 1))
        
        con.commit()
        
    def __init__(self, file_name="system_storage"):
        """
            This is used to setup any new instances of the
            class, this ensures the database is setup corrently.
        """

        # This adds the extension ".db" to the file name.
        
        file_name += ".db" 
        setup = os.path.exists(file_name)
        self._db = sql.connect(file_name, check_same_thread=False)
        
        if not setup:
            self._setup()
        con = self._db
        
        self._db.commit()


        