from werkzeug.security import generate_password_hash

"""
    Description:
        This module is used to manage the security aspect
        of this program, this includes ensuring that all
        keys are hashed to avoid storing the keys in plain
        text, this helps to avoid people having easy access
        to the private information within the program.

    Author: 
        Jake James-Robinson

"""

def hash_password(password=""):
    """
        This uses werkzeug security to hash
        a password, this allows the hashed
        password to be stored as a hash instead
        of plain text.
    """

    return generate_password_hash(password, "sha256", 1024)

