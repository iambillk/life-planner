# Life Management System - "Billas Planner 1.0 Beta"

A comprehensive Flask-based personal management application with drill sergeant motivation for tracking equipment maintenance, projects, health metrics, daily tasks, financial spending, real estate properties, and personal goals.

## 🎯 Overview

This is a full-featured personal life management system built with Flask and SQLAlchemy. It features a unique "drill sergeant" motivation system with customizable harassment levels to keep you accountable and productive.

### Core Modules

- **Daily Command Center** - Daily planner with lockout system and human maintenance tracking
- **Equipment Management** - Comprehensive vehicle and tool maintenance tracking
- **Project Management** - Dual system for work (TCH) and personal projects
- **Health Tracking** - Weight tracking with accountability features
- **Financial Tracking** - Spending analysis and budget management
- **Real Estate Management** - Property and maintenance tracking
- **Goal Setting** - Personal goal tracking with progress monitoring
- **Todo Lists** - Multi-list todo management system
- **Weekly Planning** - Week-based planning and review tools

## 🚀 Key Features

### Daily Command Center (The Drill Sergeant System)
- **Lockout System**: Must complete morning biological minimums (meds, shower, teeth, breakfast) to unlock projects
- **Project Rotation**: Automatically selects 5 projects daily based on neglect and deadlines
- **Calendar System**: 
  - Week and month views
  - Event management with edit/delete
  - Recurring events support
  - Family member tracking (Me/Wife/Kids/Family)
- **Human Maintenance Tracking**: Medications, meals, hygiene, water intake
- **Evening Review**: Daily grading system with performance metrics
- **Harassment Levels**: GENTLE, FIRM, BRUTAL, SAVAGE messaging
- **Quick Notes Capture**: Categorized note-taking system

### Equipment Management Module
- **Equipment Categories**: Auto, ATV, Marine, Tools, Motorcycle, Industrial, Farm
- **Comprehensive Tracking**:
  - Service history with photo documentation
  - Fuel logs with MPG calculations
  - Consumables and parts inventory
  - Car wash logs (Auto only)
  - Total Cost of Ownership (TCO) analysis
- **Multi-photo Support**: Before/after photos, receipts, documentation
- **Maintenance Reminders**: Service interval calculations
- **Vendor Management**: Track service providers and locations

### Project Management
- **Dual Project Systems**:
  - TCH Projects (Work/Professional)
  - Personal Projects (Home/Hobby)
- **Features per Project**:
  - Task management with categories
  - Milestone tracking
  - Ideas capture board
  - Project notes
  - File attachments
  - Progress tracking
  - Deadline management

### Health Module (The Accountability System)
- **Weight Tracking**:
  - Daily weigh-ins with time tracking
  - Failure logging system
  - Weekly/monthly statistics
  - Goal setting with daily targets
- **Accountability Features**:
  - Soda consumption tracking
  - Exercise logging
  - Water intake monitoring
  - BMI calculations
  - Trend analysis

### Financial Module
- **Transaction Management**: Income and expense tracking
- **Category System**: Customizable spending categories
- **Merchant Management**: Alias system for consistent naming
- **Analytics**: Monthly summaries and spending patterns
- **Receipt Storage**: Photo documentation support

### Real Estate Management
- **Property Tracking**: Multiple properties with details
- **Maintenance Records**: Service history with photos
- **Vendor Database**: Contractor and service provider management
- **Template System**: Recurring maintenance templates

## 🛠️ Technology Stack

- **Backend**: Flask 3.0.0
- **Database**: SQLAlchemy 3.1.1 with SQLite
- **Frontend**: Jinja2 templates, vanilla JavaScript
- **Styling**: Custom dark theme CSS with gradient effects
- **File Handling**: Local storage for photos/documents
- **Python**: 3.8+ required

## 📋 Prerequisites

- Python 3.8 or higher
- pip package manager
- Virtual environment (strongly recommended)
- 500MB free disk space for database and uploads

## 🔧 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/life-management-system.git
cd life-management-system
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Initialize Database
```bash
python
>>> from app import create_app
>>> from models.base import db
>>> app = create_app()
>>> with app.app_context():
...     db.create_all()
...     from models.daily_planner import init_daily_planner
...     init_daily_planner()
>>> exit()
```

### 5. Run the Application
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 📁 Project Structure

```
life-management-system/
├── app.py                      # Application factory and main entry
├── config.py                   # Configuration settings
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── API_DOCUMENTATION.txt       # API endpoint documentation
│
├── models/                     # Database models
│   ├── __init__.py            # Model initialization
│   ├── base.py                # Base database config
│   ├── daily_planner.py       # Daily planner models
│   ├── equipment.py           # Equipment models
│   ├── projects.py            # TCH project models
│   ├── persprojects.py        # Personal project models
│   ├── health.py              # Health tracking models
│   ├── financial.py           # Financial models
│   ├── realestate.py          # Real estate models
│   ├── goals.py               # Goal models
│   └── todo.py                # Todo list models
│
├── modules/                    # Application modules (blueprints)
│   ├── daily/                 # Daily command center
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── equipment/             # Equipment management
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── utils.py
│   │   └── constants.py
│   ├── projects/              # TCH projects
│   ├── persprojects/          # Personal projects
│   ├── health/                # Health tracking
│   ├── financial/             # Financial tracking
│   ├── realestate/            # Real estate
│   ├── goals/                 # Goal management
│   ├── todo/                  # Todo lists
│   └── weekly/                # Weekly planning
│
├── templates/                  # Jinja2 templates
│   ├── base.html              # Base template
│   ├── daily/                 # Daily planner templates
│   │   ├── dashboard.html
│   │   ├── calendar_week.html
│   │   ├── calendar_month.html
│   │   ├── add_event.html
│   │   ├── edit_event.html
│   │   └── settings.html
│   ├── equipment/             # Equipment templates
│   ├── projects/              # Project templates
│   └── ...                    # Other module templates
│
└── static/                     # Static files
    ├── css/                   # Stylesheets
    ├── js/                    # JavaScript
    └── uploads/               # User uploads
        ├── equipment_profiles/
        ├── maintenance_photos/
        ├── property_profiles/
        ├── property_maintenance/
        ├── personal_project_files/
        └── receipts/
```

## 🎮 Usage Guide

### First Time Setup

1. **Configure Settings**: Navigate to `/daily/settings` to customize:
   - Harassment level (GENTLE to SAVAGE)
   - Number of daily projects (default: 5)
   - Morning lockout requirements
   - Evening review hours

2. **Add Base Data**:
   - Create equipment entries for vehicles/tools
   - Set up initial projects (work and personal)
   - Configure health goals
   - Add spending categories

3. **Daily Workflow**:
   - Complete morning biological minimums
   - Review auto-selected projects
   - Track progress throughout the day
   - Complete evening review

### Navigation

- **Home**: `/` - Redirects to Daily Command Center
- **Daily Planner**: `/daily` - Main dashboard
- **Calendar**: `/daily/calendar` - Week/month views
- **Equipment**: `/equipment` - Equipment management
- **Projects**: `/projects` - Work projects
- **Personal**: `/personal` - Personal projects
- **Health**: `/health` - Health tracking
- **Financial**: `/financial` - Spending tracker
- **Properties**: `/property` - Real estate management

## 💾 Database Schema

The application uses SQLite with SQLAlchemy ORM. Key models include:

- **DailyConfig**: System configuration
- **CalendarEvent**: Calendar events
- **HumanMaintenance**: Daily biological tracking
- **Equipment**: Equipment/vehicle records
- **MaintenanceRecord**: Service history
- **TCHProject/PersonalProject**: Project management
- **WeightEntry**: Health tracking
- **Transaction**: Financial records
- **Property**: Real estate records

## 🔒 Security Notes

⚠️ **Important**: This application is designed for personal use and does not include authentication. Before deploying publicly:

1. Add user authentication system
2. Implement role-based access control
3. Use environment variables for sensitive config
4. Enable HTTPS in production
5. Configure proper CORS headers
6. Implement rate limiting

## 🐛 Troubleshooting

### Common Issues

1. **Database not found**: Run the initialization script in step 4
2. **Upload errors**: Check folder permissions in `/static/uploads/`
3. **Module import errors**: Ensure virtual environment is activated
4. **Port already in use**: Change port in `app.py` or kill existing process

### Reset Database
```bash
rm planner.db
python
>>> from app import create_app
>>> from models.base import db
>>> app = create_app()
>>> with app.app_context():
...     db.create_all()
```

## 📝 Contributing

This is a personal project, but suggestions are welcome:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a pull request

## 📄 License

This project is for personal use. Please contact the author for licensing information.

## 🙏 Acknowledgments

- Flask community for excellent documentation
- SQLAlchemy for powerful ORM capabilities
- Dark theme inspiration from modern development tools

## 📞 Support

For issues or questions:
- call your pimp, bitches!

---

**Version**: 1.3.1  
**Last Updated**: September 2025  
**Status**: Beta - Active Dev