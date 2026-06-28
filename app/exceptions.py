from flask import jsonify


class APIError(Exception):
    def __init__(self, message, status_code=400, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_response(self):
        body = {'erro': self.message}
        if self.payload:
            body.update(self.payload)
        return jsonify(body), self.status_code
