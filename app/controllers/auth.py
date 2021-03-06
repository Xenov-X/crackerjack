from flask import Blueprint
from flask_login import login_user, logout_user, current_user
from flask import render_template, redirect, url_for, flash, request
from app.lib.models.user import UserModel
from sqlalchemy import and_, func
from app.lib.base.provider import Provider
from werkzeug.urls import url_parse
import urllib


bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home.index'))

    return render_template('auth/login.html', next=request.args.get('next', ''))


@bp.route('/login', methods=['POST'])
def login_process():
    if current_user.is_authenticated:
        return redirect(url_for('home.index'))

    provider = Provider()
    ldap = provider.ldap()
    users = provider.users()
    settings = provider.settings()

    username = request.form['username']
    password = request.form['password']
    next = urllib.parse.unquote_plus(request.form['next'].strip())

    allow_logins = int(settings.get('allow_logins', 0))

    # First check if user is local. Local users take priority.
    user = UserModel.query.filter(and_(func.lower(UserModel.username) == func.lower(username), UserModel.ldap == 0)).first()
    if user:
        if not users.validate_password(user.password, password):
            flash('Invalid credentials', 'error')
            return redirect(url_for('auth.login', next=next))
    elif ldap.is_enabled() and allow_logins == 1:
        if not ldap.authenticate(username, password, True):
            flash('Invalid credentials', 'error')
            return redirect(url_for('auth.login', next=next))
        user = UserModel.query.filter(and_(func.lower(UserModel.username) == func.lower(username), UserModel.ldap == 1)).first()

        if not user:
            flash('Could not create your local account. Please contact the administrator.', 'error')
            return redirect(url_for('auth.login', next=next))
    else:
        flash('Invalid credentials', 'error')
        return redirect(url_for('auth.login', next=next))

    # If we reach this point it means that our user exists. Check if the user is active.
    if user.active is False:
        flash('Your account has been disabled by the Administrator.', 'error')
        return redirect(url_for('auth.login', next=next))

    user = users.login_session(user)
    login_user(user)
    users.record_login(user.id)

    # On every login we get the hashcat version and the git hash version.
    system = provider.system()
    system.run_updates()

    if next and url_parse(next).netloc == '':
        return redirect(next)

    return redirect(url_for('home.index'))


@bp.route('/logout', methods=['GET'])
def logout():
    provider = Provider()
    users = provider.users()

    users.logout_session(current_user.id)
    logout_user()
    return redirect(url_for('auth.login'))
