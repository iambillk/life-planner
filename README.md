# Life Management System

A comprehensive Flask-based personal management application for tracking equipment maintenance, projects, health metrics, daily tasks, and personal goals.

## 🎯 Overview

This is a full-featured personal management system built with Flask and SQLAlchemy, designed to help track and manage various aspects of life including:

- **Equipment Maintenance** - Track vehicles, tools, and equipment with detailed maintenance logs
- **Project Management** - Manage both work (TCH) and personal projects
- **Health Tracking** - Weight tracking with goals and analytics
- **Daily Tasks** - Day-to-day task management
- **Goal Setting** - Personal goal tracking and achievement
- **Todo Lists** - General todo list management

## 🚀 Features

### Equipment Management Module
- **Equipment Tracking**
  - Multiple categories (Auto, ATV, Marine, Tools, etc.)
  - Profile photos and galleries
  - Purchase history and TCO analysis
  - Current mileage/hours tracking
  
- **Maintenance Records**
  - Service history with costs
  - Multi-photo support (before/after/receipts)
  - Parts tracking
  - Next service reminders
  - Service interval calculations
  
- **Fuel Tracking**
  - MPG calculations
  - Station locations
  - Trip purpose categorization
  - Receipt photo storage
  
- **Consumables & Supplies**
  - Oil, filters, fluids tracking
  - Vendor management
  - Cost analysis
  
- **Car Wash Logs** (Auto category only)
  - Service types and locations
  - Monthly spending analysis

### Project Management
- **TCH Projects** (Work projects)
  - Task management
  - Milestone tracking
  - Ideas capture
  - Project notes
  - File attachments
  
- **Personal Projects**
  - Same features as work projects
  - Separate tracking

### Health Module
- Weight entry and tracking
- Weekly/monthly change calculations
- Historical data views
- Basic statistics

### Other Modules
- **Daily Tasks** - Daily task planning and tracking
- **Goals** - Personal goal setting and monitoring
- **Todo Lists** - General todo management
- **Weekly Planning** - Week-based planning tools

## 🛠️ Technology Stack

- **Backend**: Flask 2.x
- **Database**: SQLAlchemy ORM with SQLite
- **Frontend**: Jinja2 templates, vanilla JavaScript
- **Styling**: Custom CSS with dark theme
- **File Handling**: Local file storage for photos/documents

## 📋 Prerequisites

- Python 3.8+
- pip package manager
- Virtual environment (recommended)

## 🔧 Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/life-management-system.git
cd life-management-system
```

2. **Create and activate virtual environment**
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Initialize the database**
```bash
python
>>> from app import create_app
>>> app = create_app()
>>> with app.app_context():
...     from models.base import db
...     db.create_all()
>>> exit()
```

5. **Run the application**
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 📁 Project Structure

```
life-management-system/
│
├── app.py                 # Application factory and configuration
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
│
├── models/               # Database models
│   ├── __init__.py
│   ├── base.py          # Base database configuration
│   ├── equipment.py     # Equipment-related models
│   ├── projects.py      # Project models
│   ├── health.py        # Health tracking models
│   ├── daily.py         # Daily task models
│   ├── goals.py         # Goal models
│   └── todo.py          # Todo list models
│
├── modules/              # Application modules (blueprints)
│   ├── equipment/       # Equipment management
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── utils.py
│   │   └── constants.py
│   ├── projects/        # Project management
│   ├── health/          # Health tracking
│   ├── daily/           # Daily tasks
│   ├── goals/           # Goal tracking
│   ├── todo/            # Todo lists
│   └── weekly/          # Weekly planning
│
├── templates/            # Jinja2 templates
│   ├── base.html        # Base template
│   ├── dashboard.html   # Main dashboard
│   ├── equipment/       # Equipment templates
│   ├── projects/        # Project templates
│   └── ...              # Other module templates
│
└── static/              # Static files
    ├── css/            # Stylesheets
    ├── js/             # JavaScript files
    └── uploads/        # User uploads
        ├── equipment_profiles/
        ├── maintenance_photos/
        └── receipts/
```

## 💾 Database Schema

### Key Models

- **Equipment**: Vehicles, tools, and equipment
- **MaintenanceRecord**: Service history and maintenance logs
- **FuelLog**: Fuel purchases and MPG tracking
- **ConsumableLog**: Parts and supplies tracking
- **CarWashLog**: Car wash history
- **TCHProject/PersonalProject**: Project management
- **WeightEntry**: Weight tracking data
- **DailyTask**: Daily task items
- **Goal**: Personal goals
- **TodoList/TodoItem**: Todo management

## 🎨 Features in Detail

### Equipment Dashboard
- Visual alerts for overdue maintenance
- Upcoming maintenance reminders
- Equipment categorization
- Quick access to add new records

### Maintenance Tracking
- Comprehensive service logging
- Photo documentation (before/after/receipts)
- Cost tracking and analysis
- Service interval management
- Parts and supplies tracking

### Cost Analysis
- Total Cost of Ownership (TCO)
- Cost per mile/hour calculations
- Monthly spending breakdowns
- Category-wise expense analysis

### File Management
- Profile photos for equipment
- Multiple photos per maintenance record
- Receipt storage and organization
- Secure file upload handling

## 🔒 Security Considerations

- File upload validation and sanitization
- Secure filename generation
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention in templates

## 🚦 Usage

1. **Adding Equipment**
   - Navigate to Equipment Center
   - Click "Add Equipment"
   - Fill in details and upload photo
   - Save to create equipment profile

2. **Logging Maintenance**
   - Select equipment from dashboard
   - Click "Add Maintenance"
   - Enter service details and costs
   - Upload photos if desired
   - Set next service reminder

3. **Tracking Fuel**
   - Go to equipment detail page
   - Select "Add Fuel"
   - Enter purchase details
   - System calculates MPG automatically

4. **Viewing Analytics**
   - Access Cost Analysis from equipment page
   - View TCO and spending trends
   - Export maintenance history as PDF

## 🐛 Recent Bug Fixes

- Fixed maintenance edit button redirect issue (indentation error in routes.py)
- Corrected next_service_date preservation during edits
- Resolved photo upload handling in maintenance records

## 📝 TODO / Roadmap

- [ ] Enhanced weight tracking with body measurements
- [ ] Progress photo management for health module
- [ ] Mobile responsive design improvements
- [ ] Data export functionality (CSV/Excel)
- [ ] Backup and restore features
- [ ] User authentication system
- [ ] Multi-user support
- [ ] API development for mobile apps
- [ ] Integration with smart devices (scales, fitness trackers)
- [ ] Advanced reporting and analytics

## 🤝 Contributing

This is currently a personal project, but suggestions and feedback are welcome!

## 📄 License

This project is for personal use. Please contact the author for any usage beyond personal reference.

## 👤 Author

[Your Name]

## 🙏 Acknowledgments

- Flask community for excellent documentation
- SQLAlchemy for robust ORM functionality
- All open-source contributors whose libraries made this possible

---

**Last Updated**: September 2025
**Version**: 1.2.0
