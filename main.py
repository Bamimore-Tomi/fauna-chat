import hashlib,os
import datetime, pytz
from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_socketio import SocketIO
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient
from dotevn import load_dotenv
load_dotenv()

client = FaunaClient(secret=os.getenv("FAUNA_KEY"))
app = Flask(__name__)
app.config["SECRET_KEY"] = "vnkdjnfjknfl1232#"
socketio = SocketIO(app)

@app.route("/", methods=["GET","POST"])
def sessions():
    return render_template("chat.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method=="POST":
        email = request.form["email"].strip().lower()
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        try:
           user = client.query(q.get(q.match(q.index("users_index"), username)))
           flash("User already exists with that username.")
           return redirect(url_for("login"))
        except:
            user = client.query(q.create(q.collection("users"), {
                "data": {
                    "username": username,
                    "email": email,
                    "password": hashlib.sha512(password.encode()).hexdigest(),
                    "date": datetime.datetime.now(pytz.UTC)
                }
            }))
            flash("Registration successful.")
            return redirect(url_for("login"))
    return render_template("auth.html")

@app.route("/login",methods=["GET","POST"])
def login():
   if request.method == "POST":
       email = request.form["email"].strip().lower()
       password = request.form["password"]

       try:
           user = client.query(q.get(q.match(q.index("user_index"),email )))
           print(user)
           if hashlib.sha512(password.encode()).hexdigest() == user["data"]["password"]:
               session["user"] = {
                   "id": user["ref"].id(),
                   "username": user["data"]["username"]
               }
               return redirect(url_for("chat"))
           else:
               raise Exception()
       except Exception as e:
           print(e)
           flash("You have supplied invalid login credentials, please try again!")
           return redirect(url_for("login"))
   return render_template("auth.html")


@app.route("/chat", methods=["GET","POST"])
def chat():
    return render_template("clean_chat.html")

@socketio.on("outgoing")
def handle_my_custom_event(json, methods=["GET", "POST"]):
    print("received my event: " + str(json))
    socketio.emit("message", json)
if __name__ == "__main__":
    socketio.run(app, debug=True)