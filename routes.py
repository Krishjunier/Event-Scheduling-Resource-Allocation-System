from flask import Blueprint, request, jsonify
from extensions import db
from models import Resource, Event, EventResourceAllocation
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__)

# --- Helpers ---
def format_date(date_str):
    if date_str.endswith('Z'):
        date_str = date_str[:-1] + '+00:00'
    return datetime.fromisoformat(date_str) # Expects ISO 8601

def check_conflict(resource_id, start_time, end_time, exclude_event_id=None):
    """
    Checks if a resource is already allocated in the given time range.
    Returns the conflicting allocation if found, else None.
    """
    query = db.session.query(EventResourceAllocation).join(Event).filter(
        EventResourceAllocation.resource_id == resource_id,
        Event.start_time < end_time,
        Event.end_time > start_time
    )
    
    if exclude_event_id:
        query = query.filter(Event.id != exclude_event_id)
        
    return query.first()

# --- Resources ---
@api_bp.route('/api/resources', methods=['GET'])
def get_resources():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_query = request.args.get('q', '', type=str)

    query = Resource.query

    if search_query:
        search = f"%{search_query}%"
        query = query.filter(
            (Resource.name.ilike(search)) | 
            (Resource.type.ilike(search))
        )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'items': [r.to_dict() for r in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
        'per_page': pagination.per_page
    })

@api_bp.route('/api/resources', methods=['POST'])
def create_resource():
    data = request.json
    name = data.get('name')
    type_ = data.get('type')

    if not name or not type_:
        return jsonify({"error": "Resource name and type are required"}), 400

    # Check for duplicate name
    if Resource.query.filter_by(name=name).first():
        return jsonify({"error": "Resource with this name already exists"}), 409

    new_resource = Resource(name=name, type=type_)
    db.session.add(new_resource)
    db.session.commit()
    return jsonify(new_resource.to_dict()), 201

@api_bp.route('/api/resources/<int:id>', methods=['PUT'])
def update_resource(id):
    resource = Resource.query.get_or_404(id)
    data = request.json
    
    if 'name' in data:
        # Check for duplicate if name is changing
        if data['name'] != resource.name and Resource.query.filter_by(name=data['name']).first():
             return jsonify({"error": "Resource with this name already exists"}), 409
        resource.name = data['name']
        
    if 'type' in data:
        resource.type = data['type']
        
    db.session.commit()
    return jsonify(resource.to_dict())

@api_bp.route('/api/resources/<int:id>', methods=['DELETE'])
def delete_resource(id):
    resource = Resource.query.get_or_404(id)
    # Manually delete allocations first (Cascade)
    EventResourceAllocation.query.filter_by(resource_id=id).delete()
    db.session.delete(resource)
    db.session.commit()
    return jsonify({"message": "Resource deleted successfully"}), 200

@api_bp.route('/api/events', methods=['GET'])
def get_events():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_query = request.args.get('q', '', type=str)
    order = request.args.get('order', 'desc', type=str)
    upcoming_only = request.args.get('upcoming', 'false', type=str).lower() == 'true'

    query = Event.query

    if search_query:
        search = f"%{search_query}%"
        query = query.filter(
            (Event.title.ilike(search)) | 
            (Event.description.ilike(search))
        )

    if upcoming_only:
        query = query.filter(Event.start_time >= datetime.now())

    # Order by start time
    if order == 'asc':
        query = query.order_by(Event.start_time.asc())
    else:
        query = query.order_by(Event.start_time.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'items': [e.to_dict() for e in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
        'per_page': pagination.per_page
    })

@api_bp.route('/api/events', methods=['POST'])
def create_event():
    data = request.json
    try:
        start = format_date(data['start_time'])
        end = format_date(data['end_time'])
        
        if start >= end:
             return jsonify({"error": "Start time must be before end time"}), 400

        # Validation: Minimum duration 30 minutes
        if (end - start).total_seconds() < 1800:
             return jsonify({"error": "Event must be at least 30 minutes long"}), 400

        # Validation: Single day event
        if start.date() != end.date():
             return jsonify({"error": "Event must start and end on the same day"}), 400

        title = data.get('title')
        description = data.get('description')
        
        if not title:
             return jsonify({"error": "Title is required"}), 400
             
        if not description or not description.strip():
             return jsonify({"error": "Description is mandatory"}), 400

        new_event = Event(
            title=title,
            description=description,
            start_time=start,
            end_time=end
        )
        db.session.add(new_event)
        db.session.commit()
        return jsonify(new_event.to_dict()), 201
    except ValueError:
        return jsonify({"error": "Invalid date format. Use ISO 8601"}), 400

@api_bp.route('/api/events/<int:id>', methods=['PUT'])
def update_event(id):
    event = Event.query.get_or_404(id)
    data = request.json
    
    try:
        if 'start_time' in data:
            event.start_time = format_date(data['start_time'])
        if 'end_time' in data:
            event.end_time = format_date(data['end_time'])
            
        if event.start_time >= event.end_time:
             return jsonify({"error": "Start time must be before end time"}), 400

        # Validation: Minimum duration 30 minutes
        if (event.end_time - event.start_time).total_seconds() < 1800:
             return jsonify({"error": "Event must be at least 30 minutes long"}), 400

        # Validation: Single day event
        if event.start_time.date() != event.end_time.date():
             return jsonify({"error": "Event must start and end on the same day"}), 400

        if 'title' in data:
            event.title = data['title']
        if 'description' in data:
            desc = data['description']
            if not desc or not desc.strip():
                 return jsonify({"error": "Description is mandatory"}), 400
            event.description = desc
            
        db.session.commit()
        return jsonify(event.to_dict())
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

@api_bp.route('/api/events/<int:id>', methods=['DELETE'])
def delete_event(id):
    event = Event.query.get_or_404(id)
    # Manually delete allocations first (Cascade)
    EventResourceAllocation.query.filter_by(event_id=id).delete()
    db.session.delete(event)
    db.session.commit()
    return jsonify({"message": "Event deleted successfully"}), 200

# --- Allocations ---
@api_bp.route('/api/allocations', methods=['POST'])
def allocate_resource():
    data = request.json
    event_id = data['event_id']
    resource_id = data['resource_id']
    
    event = Event.query.get_or_404(event_id)
    resource = Resource.query.get_or_404(resource_id)
    
    # Check if already allocated
    existing_allocation = EventResourceAllocation.query.filter_by(event_id=event_id, resource_id=resource_id).first()
    if existing_allocation:
        return jsonify({"error": "Resource already allocated to this event"}), 409

    # Check for conflict
    conflict = check_conflict(resource_id, event.start_time, event.end_time, exclude_event_id=event_id)
    if conflict:
        # Retrieve conflicting event details for better error message
        conflicting_event = Event.query.get(conflict.event_id)
        return jsonify({
            "error": "Resource conflict detected",
            "details": f"Resource '{resource.name}' is already booked for '{conflicting_event.title}' from {conflicting_event.start_time} to {conflicting_event.end_time}"
        }), 409
        
    allocation = EventResourceAllocation(event_id=event_id, resource_id=resource_id)
    try:
        db.session.add(allocation)
        db.session.commit()
        return jsonify(allocation.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

# --- Reports ---
@api_bp.route('/api/reports/utilization', methods=['GET'])
def utilization_report():
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    if not start_str or not end_str:
        return jsonify({"error": "Please provide start_date and end_date"}), 400
        
    try:
        # Convert to naive datetime to match database (SQLAlchemy returns naive)
        report_start = format_date(start_str).replace(tzinfo=None)
        report_end = format_date(end_str).replace(tzinfo=None)
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    # Logic: For each resource, calculate total duration of allocated events within the range
    # We only count the overlapping duration if the event is partially in the range
    
    query = db.session.query(Resource, Event).select_from(Resource).join(EventResourceAllocation).join(Event).filter(
        Event.start_time < report_end,
        Event.end_time > report_start
    ).all()
    
    resource_stats = {}
    
    for res, evt in query:
        # Calculate overlap
        overlap_start = max(report_start, evt.start_time)
        overlap_end = min(report_end, evt.end_time)
        duration_seconds = (overlap_end - overlap_start).total_seconds()
        
        if res.id not in resource_stats:
            resource_stats[res.id] = {
                "resource_name": res.name,
                "total_hours": 0,
                "bookings": 0
            }
        
        resource_stats[res.id]["total_hours"] += duration_seconds / 3600
        resource_stats[res.id]["bookings"] += 1
        
    return jsonify(list(resource_stats.values()))

@api_bp.route('/api/reports/export', methods=['GET'])
def export_report_pdf():
    from fpdf import FPDF
    import io
    from flask import send_file

    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    if not start_str or not end_str:
        return jsonify({"error": "Please provide start_date and end_date"}), 400

    try:
        report_start = format_date(start_str).replace(tzinfo=None)
        report_end = format_date(end_str).replace(tzinfo=None)
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    # reusing aggregation logic (could be refactored into a helper function)
    query = db.session.query(Resource, Event).select_from(Resource).join(EventResourceAllocation).join(Event).filter(
        Event.start_time < report_end,
        Event.end_time > report_start
    ).all()
    
    resource_stats = {}
    for res, evt in query:
        overlap_start = max(report_start, evt.start_time)
        overlap_end = min(report_end, evt.end_time)
        duration_seconds = (overlap_end - overlap_start).total_seconds()
        
        if res.id not in resource_stats:
            resource_stats[res.id] = { "resource_name": res.name, "total_hours": 0, "bookings": 0 }
        
        resource_stats[res.id]["total_hours"] += duration_seconds / 3600
        resource_stats[res.id]["bookings"] += 1

    # Sanitize helper for FPDF (latin-1)
    def sanitize(text):
        if not text: return ""
        return str(text).replace('\u2013', '-').replace('\u2014', '--').encode('latin-1', 'replace').decode('latin-1')

    # Prepare Data for Charts
    import matplotlib
    matplotlib.use('Agg') # Use non-interactive backend
    import matplotlib.pyplot as plt
    import tempfile
    import os

    resource_names = []
    total_hours = []
    bookings_count = []
    
    # Sort data for better visualization
    sorted_data = sorted(list(resource_stats.values()), key=lambda x: x['total_hours'], reverse=True)
    
    for item in sorted_data:
        resource_names.append(item['resource_name'])
        total_hours.append(item['total_hours'])
        bookings_count.append(item['bookings'])

    # 1. Bar Chart: Utilization per Resource
    plt.figure(figsize=(10, 6))
    plt.bar(resource_names, total_hours, color='skyblue')
    plt.xlabel('Resources')
    plt.ylabel('Total Hours')
    plt.title('Resource Utilization (Hours)')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_bar:
        plt.savefig(tmp_bar.name, format='png', dpi=100)
        bar_chart_path = tmp_bar.name
    plt.close()

    # 1b. Bar Chart: Bookings per Resource
    plt.figure(figsize=(10, 6))
    plt.bar(resource_names, bookings_count, color='lightgreen')
    plt.xlabel('Resources')
    plt.ylabel('Bookings Count')
    plt.title('Resource Bookings (Count)')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_booking:
        plt.savefig(tmp_booking.name, format='png', dpi=100)
        booking_chart_path = tmp_booking.name
    plt.close()

    # 2. Pie Chart: Usage by Type
    # Aggregate by type first (need to fetch type in query or re-query)
    # Re-querying specifically for Chart aggregation to be safe and simple
    type_results = db.session.query(
        Resource.type, 
        db.func.sum(
            db.func.timestampdiff(db.text('SECOND'), Event.start_time, Event.end_time)
        )
    ).select_from(Resource).join(EventResourceAllocation).join(Event).filter(
        Event.start_time < report_end,
        Event.end_time > report_start
    ).group_by(Resource.type).all()

    type_labels = []
    type_sizes = []
    for r_type, total_seconds in type_results:
        if total_seconds and total_seconds > 0:
            type_labels.append(r_type)
            type_sizes.append(float(total_seconds) / 3600)

    if type_sizes:
        plt.figure(figsize=(8, 8))
        plt.pie(type_sizes, labels=type_labels, autopct='%1.1f%%', startangle=140, colors=plt.cm.Pastel1.colors)
        plt.title('Usage by Resource Type')
        plt.tight_layout()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_pie:
            plt.savefig(tmp_pie.name, format='png', dpi=100)
            pie_chart_path = tmp_pie.name
        plt.close()
    else:
        pie_chart_path = None

    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Resource Utilization Report", ln=1, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=sanitize(f"From {start_str} to {end_str}"), ln=1, align='C')
    pdf.ln(10)

    # Embed Bar Chart (Hours)
    if resource_names:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Resource Utilization (Hours)", ln=1, align='L')
        # PDF Image: x, y, w, h
        pdf.image(bar_chart_path, x=10, y=None, w=190)
        pdf.ln(5)
        
        # Embed Bar Chart (Bookings) - New Page
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Resource Bookings (Count)", ln=1, align='L')
        pdf.image(booking_chart_path, x=10, y=None, w=190)
        pdf.ln(5)

    else:
        pdf.cell(200, 10, txt="No data available for bar chart.", ln=1, align='C')

    # Embed Pie Chart
    if pie_chart_path:
        pdf.add_page() # New page for Pie chart
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Usage by Resource Type", ln=1, align='L')
        pdf.image(pie_chart_path, x=30, y=None, w=150)
    
    # Output - Generate PDF bytes BEFORE deleting temp files
    try:
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        print(f"PDF Output Error: {e}")
        return jsonify({"error": "Failed to generate PDF"}), 500
    
    # Cleanup Temp Files
    try:
        if 'bar_chart_path' in locals() and os.path.exists(bar_chart_path): 
            os.remove(bar_chart_path)
        if 'booking_chart_path' in locals() and os.path.exists(booking_chart_path):
            os.remove(booking_chart_path)
        if 'pie_chart_path' in locals() and pie_chart_path and os.path.exists(pie_chart_path): 
            os.remove(pie_chart_path)
    except Exception as e:
        print(f"Cleanup Error: {e}")

    pdf_buffer = io.BytesIO()
    pdf_buffer.write(pdf_bytes)
    pdf_buffer.seek(0)
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"report_{start_str}_{end_str}.pdf",
        mimetype='application/pdf'
    )

@api_bp.route('/api/reports/usage-by-type', methods=['GET'])
def report_usage_by_type():
    # Aggregate total hours by resource type for ALL time (or default range?)
    # usually usage by type is an overview metric. Let's do all time or last 30 days.
    # For dashboard, "All Time" or "Current Month" is good. Let's do All Time for simplicity of "Usage".
    
    # Logic: Join Resource, Allocation, Event. Group by Resource.type. Sum duration.
    results = db.session.query(
        Resource.type, 
        db.func.sum(
            db.func.timestampdiff(db.text('SECOND'), Event.start_time, Event.end_time)
        )
    ).select_from(Resource).join(EventResourceAllocation).join(Event).group_by(Resource.type).all()
    
    data = []
    for r_type, total_seconds in results:
        # total_seconds might be Decimal or None
        hours = (total_seconds or 0) / 3600
        data.append({
            "type": r_type,
            "hours": float(hours)
        })
        
    return jsonify(data)
