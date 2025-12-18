from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)

@views_bp.route('/')
def dashboard():
    return render_template('dashboard.html', page='dashboard')

@views_bp.route('/resources')
def resources():
    return render_template('resources.html', page='resources')

@views_bp.route('/events')
def events():
    return render_template('events.html', page='events')

@views_bp.route('/allocations')
def allocations():
    return render_template('allocations.html', page='allocations')

@views_bp.route('/reports')
def reports():
    return render_template('reports.html', page='reports')


