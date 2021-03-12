import uuid
import hashlib, time


class Hash:
    def __init__(self):
        self.hash = ''

    def hash_password(self, password):
        salt = uuid.uuid4().hex
        return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt

    def set_hash(self, user_hash):
        self.hash = user_hash

    def check_password(self, user_password):
        if self.hash == '':
            return
        password, salt = self.hash.split(':')
        return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()
