import threading
import time

from flask import Flask, _app_ctx_stack, _request_ctx_stack
from flask_sqlalchemy import SQLAlchemy

from dimensigon.web import Executor


def scopefunc():
    try:
        return str(id(_app_ctx_stack.top.app)) + str(threading.get_ident()) + str(id(_request_ctx_stack.top.request))
    except:
        try:
            return str(id(_app_ctx_stack.top.app)) + str(threading.get_ident())
        except:
            return str(threading.get_ident())

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['EXECUTOR_MAX_WORKERS'] = 5
db = SQLAlchemy(app, session_options=dict(scopefunc=scopefunc),)
executor = Executor(app, )

def execution():
    time.sleep(5)
    print(User.query.one())

@app.route('/users')
def users():
    users = {}
    executor.submit(execution)
    [users.update(id=u.id, name=u.username) for u in User.query.all()]
    return users

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return '<User %r>' % self.username

db.create_all()

u = User.query.get(1)
if not u:
    u = User()
    u.id = 1
    u.username = 'joan'
    u.email = 'joan@domain.com'
    db.session.add(u)
    db.session.commit()

if __name__ == '__main__':
    app.run(port=3000)