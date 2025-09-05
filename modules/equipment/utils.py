import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_uploaded_photo(file, folder_type, base_name):
    """Save uploaded photo and return filename"""
    import uuid
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + str(uuid.uuid4())[:8]
    extension = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{secure_filename(base_name)}_{timestamp}.{extension}"
    
    if folder_type == 'maintenance_photos':
        # Create year/month folders for maintenance photos
        year_month = datetime.now().strftime('%Y/%m')
        folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_type, year_month)
        os.makedirs(folder_path, exist_ok=True)
        filepath = os.path.join(folder_path, filename)
        file.save(filepath)
        return f"{year_month}/{filename}"
    else:
        # Equipment profile photos
        folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_type)
        filepath = os.path.join(folder_path, filename)
        file.save(filepath)
        return filename

def get_maintenance_alerts(equipment_list):
    """Get overdue and upcoming maintenance alerts"""
    from models import MaintenanceRecord
    
    overdue = []
    upcoming = []
    today = datetime.now().date()
    
    for equip in equipment_list:
        last_maintenance = MaintenanceRecord.query.filter_by(
            equipment_id=equip.id
        ).order_by(MaintenanceRecord.service_date.desc()).first()
        
        if last_maintenance and last_maintenance.next_service_date:
            days_until = (last_maintenance.next_service_date - today).days
            if days_until < 0:
                overdue.append({
                    'equipment': equip,
                    'service': last_maintenance.service_type,
                    'days_overdue': abs(days_until)
                })
            elif days_until <= 30:
                upcoming.append({
                    'equipment': equip,
                    'service': last_maintenance.service_type,
                    'days_until': days_until
                })
    
    return overdue, upcoming

def generate_maintenance_pdf(equipment, maintenance_records):
    """Generate PDF of maintenance history"""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    
    # Title
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(50, 750, f"Maintenance History: {equipment.name}")
    
    # Equipment details
    pdf.setFont("Helvetica", 12)
    y_position = 700
    
    details = [
        f"Category: {equipment.category}",
        f"Make: {equipment.make or 'N/A'}",
        f"Model: {equipment.model or 'N/A'}",
        f"Year: {equipment.year or 'N/A'}",
        f"Serial: {equipment.serial_number or 'N/A'}"
    ]
    
    if equipment.mileage:
        details.append(f"Current Mileage: {equipment.mileage:,}")
    if equipment.hours:
        details.append(f"Current Hours: {equipment.hours}")
    
    for detail in details:
        pdf.drawString(50, y_position, detail)
        y_position -= 20
    
    # Maintenance records
    y_position -= 20
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y_position, "Service History")
    y_position -= 20
    
    pdf.setFont("Helvetica", 10)
    for record in maintenance_records:
        if y_position < 100:
            pdf.showPage()
            y_position = 750
            pdf.setFont("Helvetica", 10)
        
        pdf.drawString(50, y_position, f"Date: {record.service_date.strftime('%m/%d/%Y')}")
        pdf.drawString(200, y_position, f"Service: {record.service_type}")
        pdf.drawString(400, y_position, f"Cost: ${record.cost:.2f}" if record.cost else "Cost: N/A")
        y_position -= 15
        
        if record.notes:
            pdf.drawString(70, y_position, f"Notes: {record.notes[:80]}")
            y_position -= 15
        
        if record.mileage_at_service:
            pdf.drawString(70, y_position, f"Mileage: {record.mileage_at_service:,}")
            y_position -= 15
        
        y_position -= 10
    
    # Footer
    pdf.setFont("Helvetica", 8)
    pdf.drawString(50, 50, f"Generated: {datetime.now().strftime('%m/%d/%Y %I:%M %p')}")
    
    pdf.save()
    buffer.seek(0)
    return buffer