from flask import Flask, redirect, url_for, render_template, request, session, flash
from datetime import timedelta
import datetime
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class Task:
    task_id_counter = 0

    def __init__(self, title, description, status, date):
        Task.task_id_counter += 1
        self.id = Task.task_id_counter
        self.title = title
        self.description = description
        self.status = status
        self.date = date

    def time_to_complete(self):
        if not self.status:
            return f"Time to complete: {days_until(self.date)} days"
        else:
            return "Completed"


def string_to_date(date_string, date_format="%Y-%m-%d"):
    return datetime.datetime.strptime(date_string, date_format).date()


def date_to_human_readable(date_obj):
    if isinstance(date_obj, str):
        # Assuming the date string is in 'YYYY-MM-DD' format
        date_obj = datetime.datetime.strptime(date_obj, "%Y-%m-%d").date()
    return date_obj.strftime("%d. %m. %Y")


def days_until(target_date):
    today = datetime.date.today()
    if isinstance(target_date, str):
        target_date = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()  # Convert string to date if necessary
    remaining_days = (target_date - today).days
    return remaining_days






app = Flask(__name__)
app.secret_key = "hello"
app.permanent_session_lifetime = timedelta(minutes=5)

app.jinja_env.filters['date_to_human_readable'] = date_to_human_readable
app.jinja_env.filters['days_until'] = days_until

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tasks.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Taskdb(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # 'pending', 'completed'
    date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    tasks = db.relationship('Taskdb', backref='user', lazy=True)



# def update_task_status():
#     with app.app_context():
#         today = datetime.date.today()
#         tasks_to_update = Taskdb.query.filter(Taskdb.date < today, Taskdb.status == "pending").all()
#         for task in tasks_to_update:
#             task.status = "failed"
        

#         tasks_with_one_day_left = Taskdb.query.filter(Taskdb.date == today + datetime.timedelta(days=1), Taskdb.status == "pending").all()
#         for taks in tasks_with_one_day_left:
#             user = User.query.get(taks.user_id)
#             if user and user.email:
#                 try:
#                     send_email(user.email, task)
#                     print(f"Email odeslán uživateli {user.email} pro úkol {task.title}.")
#                 except Exception as e:
#                     print(f"Chyba při odesílání emailu: {e}")
#         db.session.commit()


# @app.before_request
# def before_request_func():
#     update_task_status()


@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("user"))
    else:
        return render_template("das.html", content="Testing")


@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        found_user = User.query.filter_by(username=username, password = password).first()
        if found_user:
            session.permanent = True
            session["user"] = username
            session["user_id"] = found_user.id  # Uložení user_id do session
            session["tasks"] = []
            session["completed_tasks"] = 0
            flash("Logged in successfully")
            flash(f"Welcome, {username}!", "info")
            return redirect(url_for("user"))
        else:
            flash("Login Unsuccessful. Please check username and password", "danger")
            return redirect(url_for("login"))
    else:
        if "user" in session:
            user = session["user"]
            flash(f"Already logged in, {user}")
            return redirect(url_for("user"))
        return render_template("login.html")


@app.route("/user", methods=["GET", "POST"])
def user():
    if "user_id" in session:
        user_id = session["user_id"]
        user = User.query.get(user_id)
        pending_tasks_count = Taskdb.query.filter_by(user_id=user_id, status="pending").count()
        completed_tasks_count = Taskdb.query.filter_by(user_id=user_id, status="completed").count()
        failed_tasks_count = Taskdb.query.filter_by(user_id=user_id, status="failed").count()
        if request.method == "POST":
            task = request.form.get("task")
            if task:  # If a task is provided, add it
                if "tasks" not in session:  # Ensure "tasks" key exists
                    session["tasks"] = []
                session["tasks"].append(task)  # Use "tasks" consistently
                flash(f"Task added, {task}", "info")
                session.modified = True
        tasks = session.get("tasks", [])  # Use "tasks" consistently
        return render_template("user.html", tasks=tasks, user=user, username=user.username, pending_tasks_count=pending_tasks_count, completed_tasks_count=completed_tasks_count, failed_tasks_count=failed_tasks_count)
    else:
        return redirect(url_for("login"))


@app.route("/logout")
def logout():
    if "user" in session:
        user = session["user"]
        flash(f"You have been logged out, {user}", "info")
    session.pop("user", None)
    session.pop("tasks", None)
    return redirect(url_for("login"))


@app.route("/viewtasks", methods=["GET", "POST"])
def viewtasks():
    if "user" not in session:
        flash("You are not logged in!")
        return redirect(url_for("login"))
    if "user_id" in session:
        user_id = session["user_id"]
        user = User.query.get(user_id)
        tasks = Taskdb.query.filter_by(user_id=user_id, status="pending").all()  # Načtení všech úkolů pro uživatele
        return render_template("viewtasks.html", tasks=tasks, user=user, username=user.username)

    else:
        flash("You are not logged in!")
        return redirect(url_for("login"))


completed_tasks = 0


@app.route("/complete_task/<int:task_id>", methods=["POST"])
def complete_task(task_id):
    task_to_complete = Taskdb.query.get(task_id)
    if task_to_complete:
        task_to_complete.status = "completed"
        db.session.commit()
        flash("Congratulations! You have completed a task.", "info")
    else:
        flash("Task not found.", "error")
    return redirect(url_for('viewtasks'))


@app.route("/addtasks", methods=["GET", "POST"])
def addtasks():
    if "user" not in session:
        flash("You are not logged in!")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        date = request.form.get("date")

        if not title or not description or not date:
            flash('All fields are required.')
            return redirect(url_for('addtasks'))
        elif date < datetime.date.today().strftime("%Y-%m-%d"):
            flash('Date cannot be in the past.')
            return redirect(url_for('addtasks'))

        try:
            # Create a new Task instance
            date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
            # Předpokládáme, že session["tasks"] je seznam slovníků
            new_task = Taskdb(title=title, description=description, status="pending", date=date_obj, user_id=session['user_id'])
            db.session.add(new_task)
            db.session.commit()
            flash('Task added successfully!')
        except Exception as e:
            # Handle exceptions, such as incorrect date format
            flash(str(e))

        return redirect(url_for('addtasks'))

        # Zde byste měli přidat logiku pro ukládání úkolu, například do session nebo databáze
        # Pro jednoduchost přidáme úkol do session

    return render_template("addtasks.html")



@app.route("/create_account", methods=["POST", "GET"])
def create_account():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.')
            return redirect(url_for('create_account'))
        new_user = User(username=username, password=password)  # Adjust for hashed password
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully!')
        return redirect(url_for('login'))
    # If the method is not POST, you might want to show the account creation page or handle differently
    return render_template("create_account.html")  # Assuming you have a template for account creation



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)
