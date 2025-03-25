from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import logging
import os
import sys  # Add sys import
import time
import jwt as pyjwt
import datetime
from datetime import timezone
from flask_migrate import Migrate
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from sqlalchemy import event
from sqlalchemy.engine import Engine
from math import radians, sin, cos, sqrt, atan2  # Add these imports

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# إعداد قاعدة البيانات
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Add SECRET_KEY for JWT token generation
app.config['SECRET_KEY'] = 'locate-me-secret-key'

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {
        'timeout': 20,
        'check_same_thread': False,
    }
}

# Remove the existing set_sqlite_pragma function and replace with this:
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout = 60000")  # 60 second timeout
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.close()
    except Exception as e:
        logger.error(f"Error setting SQLite pragmas: {e}")

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# نموذء البيانات
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location
        }

# نموذء بيانات الطالب
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    embedding = db.Column(db.Text, nullable=True)  # إضافة عمود التشفير

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' or 'doctor'
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'student_id': self.student_id,
            'name': self.name,
            'role': self.role
        }

# نموذء بيانات المقررات الدراسية
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    enrollment_code = db.Column(db.String(10), unique=True, nullable=False)
    day = db.Column(db.String(50), nullable=True)
    time = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    isAttendanceOpen = db.Column(db.Boolean, default=False)

    def to_dict(self):
        students_count = StudentCourse.query.filter_by(course_id=self.id).count()
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'doctor_id': self.doctor_id,
            'students': students_count,
            'enrollment_code': self.enrollment_code,
            'day': self.day,
            'time': self.time,
            'location': self.location,
            'isAttendanceOpen': self.isAttendanceOpen  # حذف or False
        }

# نموذء العلاقة بين الطلاب والمقررات
class StudentCourse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    # لضمان عدم تكرار تسجيل الطالب في نفس المقرر
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id'),)

# Add after other models
class StudentLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# الراوترز
@app.route('/', methods=['GET'])
def health_check():
    logger.info(f"Health check endpoint called from {request.remote_addr}")
    try:
        return jsonify({
            "status": "ok",
            "server": "running",
            "database": "connected" if db.session.is_active else "disconnected"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/data', methods=['GET'])
def get_data():
    try:
        logger.info("GET request received for /data")
        locations = Location.query.all()
        return jsonify([location.to_dict() for location in locations]), 200
    except Exception as e:
        logger.error(f"Error in get_data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/data', methods=['POST'])
def add_data():
    try:
        data = request.json
        print(f"Received data: {data}")  # إضافة هذا السطر للتأكد من البيانات
        if not data or 'name' not in data or 'location' not in data:
            raise ValueError("Missing required fields 'name' or 'location'")
        new_location = Location(name=data.get('name'), location=data.get('location'))
        db.session.add(new_location)
        db.session.commit()
        print("Data saved successfully")  # وهذا السطر للتأكد من الحفظ
        return jsonify({'message': 'Added successfully'}), 201
    except Exception as e:
        print(f"Error: {e}")  # وهذا للأخطاء
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
            
        email = data.get('email')
        password = data.get('password')
        
        # Log the received data for debugging
        print(f"Login attempt with email: {email}, password type: {type(password)}")
        
        # Find the user
        user = User.query.filter_by(email=email).first()
        
        if user and user.password == password:
            # Generate JWT token
            token_payload = {
                'user_id': str(user.id),
                'exp': datetime.datetime.now(timezone.utc) + datetime.timedelta(days=1)
            }
            
            # Use pyjwt instead of jwt
            token = pyjwt.encode(
                token_payload, 
                app.config['SECRET_KEY'], 
                algorithm='HS256'
            )
            
            # If token is returned as bytes, decode to string
            if isinstance(token, bytes):
                token = token.decode('utf-8')
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'token': token,
                'user': user.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid email or password'
            }), 401
    except Exception as e:
        print(f"Error in login: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# Add this new route
@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        logger.info(f"Received signup request with data: {data}")
        
        # Validate required fields
        required_fields = ['email', 'password', 'student_id', 'name', 'role']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400

        # Check if user already exists
        existing_user = User.query.filter(
            (User.email == data['email']) | 
            (User.student_id == data['student_id'])
        ).first()
        
        if existing_user:
            return jsonify({
                'success': False,
                'message': 'Email or Student ID already registered'
            }), 400

        # Create new user
        new_user = User(
            email=data['email'],
            password=data['password'],  # TODO: Add password hashing
            student_id=data['student_id'],
            name=data['name'],
            role=data['role']
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        logger.info(f"Successfully created new user: {new_user.email}")
        return jsonify({
            'success': True,
            'message': 'Registration successful'
        }), 201
    
    except Exception as e:
        logger.error(f"Error in signup: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# إضافة مقرر دراسي جديد (للدكتور فقط)
@app.route('/courses', methods=['POST'])
def add_course():
    try:
        data = request.json
        logger.info(f"Received add course request with data: {data}")
        
        # التحقق من البيانات المطلوبة
        required_fields = ['code', 'name', 'description', 'doctor_id']
        for field in required_fields:
            if field not in data or not data[field]:
                logger.error(f"Missing required field: {field}")
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # التحقق من وجود حقول اليوم والوقت والموقع (غير إلزامية ولكن يجب التحقق منها)
        if 'day' not in data:
            data['day'] = ''
            logger.info("Day field not provided, using empty string")
        if 'time' not in data:
            data['time'] = ''
            logger.info("Time field not provided, using empty string")
        if 'location' not in data:
            data['location'] = ''
            logger.info("Location field not provided, using empty string")
        
        # التحقق من أن المستخدم دكتور
        doctor = User.query.filter_by(id=data['doctor_id'], role='doctor').first()
        if not doctor:
            logger.error(f"User with ID {data['doctor_id']} is not a doctor or does not exist")
            return jsonify({
                'success': False,
                'message': 'Unauthorized: Only doctors can add courses'
            }), 403
        
        # التحقق من عدم وجود مقرر بنفس الكود
        existing_course = Course.query.filter_by(code=data['code']).first()
        if (existing_course):
            logger.error(f"Course with code {data['code']} already exists")
            return jsonify({
                'success': False,
                'message': 'Course code already exists'
            }), 400
        
        # Generate a unique enrollment code (alphanumeric, 6 characters)
        import random
        import string
        
        def generate_enrollment_code():
            # Generate a random 6-character alphanumeric code
            chars = string.ascii_uppercase + string.digits
            code = ''.join(random.choice(chars) for _ in range(6))
            
            # Check if the code already exists
            existing = Course.query.filter_by(enrollment_code=code).first()
            if existing:
                # If code exists, generate a new one recursively
                return generate_enrollment_code()
            return code
        
        # Generate a unique enrollment code
        enrollment_code = generate_enrollment_code()
        logger.info(f"Generated enrollment code: {enrollment_code}")
        
        # إنشاء مقرر جديد
        new_course = Course(
            code=data['code'],
            name=data['name'],
            description=data['description'],
            doctor_id=data['doctor_id'],
            enrollment_code=enrollment_code,
            day=data.get('day', ''),
            time=data.get('time', ''),
            location=data.get('location', '')  # Add this line
        )
        
        logger.info(f"Attempting to add new course: {new_course.code}")
        db.session.add(new_course)
        db.session.commit()
        logger.info(f"Successfully added course to database")
        
        logger.info(f"Successfully created new course: {new_course.code} with enrollment code: {enrollment_code}")
        return jsonify({
            'success': True,
            'message': 'Course added successfully',
            'course': new_course.to_dict()
        }), 201
    
    except Exception as e:
        logger.error(f"Error in add_course: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# الحصول على مقررات الدكتور
@app.route('/courses/doctor/<int:doctor_id>', methods=['GET'])
def get_doctor_courses(doctor_id):
    try:
        # تعديل في ملف app.py:
        
        # لضمان توافق أفضل، يمكننا أيضًا تعديل ملف `app.py` للتعامل مع معرف الدكتور بشكل أكثر مرونة:
        try:
            doctor_id = int(doctor_id)
        except ValueError:
            logger.error(f"Invalid doctor_id format: {doctor_id}")
            return jsonify({
                'success': False,
                'message': 'Invalid doctor ID format'
            }), 400
            
        # التحقق من أن المستخدم دكتور
        doctor = User.query.filter_by(id=doctor_id, role='doctor').first()
        if not doctor:
            return jsonify({
                'success': False,
                'message': 'Unauthorized: Invalid doctor ID'
            }), 403
        
        # الحصول على مقررات الدكتور
        courses = Course.query.filter_by(doctor_id=doctor_id).all()
        
        return jsonify({
            'success': True,
            'courses': [course.to_dict() for course in courses]
        }), 200
    
    except Exception as e:
        logger.error(f"Error in get_doctor_courses: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# حذف مقرر دراسي (للدكتور فقط)
@app.route('/courses/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    try:
        data = request.json
        doctor_id = data.get('doctor_id')
        
        if not doctor_id:
            return jsonify({
                'success': False,
                'message': 'Missing doctor_id'
            }), 400
        
        # التحقق من وجود المقرر
        course = Course.query.get(course_id)
        if not course:
            return jsonify({
                'success': False,
                'message': 'Course not found'
            }), 404
        
        # التحقق من أن الدكتور هو مالك المقرر
        if course.doctor_id != doctor_id:
            return jsonify({
                'success': False,
                'message': 'Unauthorized: You can only delete your own courses'
            }), 403
        
        # حذف جميع علاقات الطلاب بالمقرر أولاً
        StudentCourse.query.filter_by(course_id=course_id).delete()
        
        # حذف المقرر
        db.session.delete(course)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Course deleted successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error in delete_course: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# تسجيل طالب في مقرر باستخدام كود التسجيل
@app.route('/courses/enroll', methods=['POST'])
def enroll_in_course():
    try:
        data = request.json
        student_id = data.get('student_id')  # Could be string or int
        enrollment_code = data.get('enrollment_code')  # Should be string
        
        if not student_id or not enrollment_code:
            return jsonify({
                'success': False,
                'message': 'Missing student_id or enrollment_code'
            }), 400
        
        # Always convert student_id to int for database operations
        try:
            student_id = int(student_id)
        except ValueError:
            logger.error(f"Invalid student_id format: {student_id}")
            return jsonify({
                'success': False,
                'message': 'Invalid student ID format'
            }), 400
        
        # Find the student
        student = User.query.filter_by(id=student_id, role='student').first()
        if not student:
            return jsonify({
                'success': False,
                'message': 'Unauthorized: Invalid student ID'
            }), 403
        
        # Find the course by enrollment code
        course = Course.query.filter_by(enrollment_code=enrollment_code).first()
        if not course:
            return jsonify({
                'success': False,
                'message': 'Invalid enrollment code'
            }), 404
        
        # Check if already enrolled
        existing_enrollment = StudentCourse.query.filter_by(
            student_id=student_id, 
            course_id=course.id
        ).first()
        
        if existing_enrollment:
            return jsonify({
                'success': False,
                'message': 'You are already enrolled in this course'
            }), 400
        
        # Create new enrollment
        new_enrollment = StudentCourse(
            student_id=student_id,
            course_id=course.id
        )
        
        db.session.add(new_enrollment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Successfully enrolled in course',
            'course': course.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Error in enroll_in_course: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# الحصول على مقررات الطالب
@app.route('/courses/student/<student_id>', methods=['GET'])
def get_student_courses(student_id):
    try:
        # Convert student_id to integer
        try:
            student_id = int(student_id)
        except ValueError:
            logger.error(f"Invalid student_id format: {student_id}")
            return jsonify({
                'success': False,
                'message': 'Invalid student ID format'
            }), 400
            
        # التحقق من أن المستخدم طالب
        student = User.query.filter_by(id=student_id, role='student').first()
        if not student:
            return jsonify({
                'success': False,
                'message': 'Unauthorized: Invalid student ID'
            }), 403
        
        # الحصول على معرفات المقررات المسجل فيها الطالب
        enrollments = StudentCourse.query.filter_by(student_id=student_id).all()
        course_ids = [enrollment.course_id for enrollment in enrollments]
        
        # الحصول على تفاصيل المقررات
        courses = Course.query.filter(Course.id.in_(course_ids)).all()
        
        return jsonify({
            'success': True,
            'courses': [course.to_dict() for course in courses]
        }), 200
    
    except Exception as e:
        logger.error(f"Error in get_student_courses: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# Make sure there's no incomplete try block before this line
@app.route('/courses/<int:course_id>/students', methods=['GET'])
def get_course_students(course_id):
    try:
        # التحقق من وجود المقرر
        course = Course.query.get(course_id)
        if not course:
            return jsonify({
                'success': False,
                'message': 'Course not found'
            }), 404
        
        # الحصول على معرفات الطلاب المسجلين في المقرر
        enrollments = StudentCourse.query.filter_by(course_id=course_id).all()
        student_ids = [enrollment.student_id for enrollment in enrollments]
        
        # الحصول على تفاصيل الطلاب
        students = User.query.filter(User.id.in_(student_ids)).all()
        
        return jsonify({
            'success': True,
            'students': [student.to_dict() for student in students]
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_course_students: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# إلغاء تسجيل طالب من مقرر
@app.route('/courses/unenroll', methods=['POST'])
def unenroll_from_course():
    try:
        data = request.json
        student_id = data.get('student_id')
        course_id = data.get('course_id')
        
        if not student_id or not course_id:
            return jsonify({
                'success': False,
                'message': 'Missing student_id or course_id'
            }), 400
        
        # التحقق من أن المستخدم طالب
        student = User.query.filter_by(id=student_id, role='student').first()
        if not student:
            return jsonify({
                'success': False,
                'message': 'Unauthorized: Invalid student ID'
            }), 403
        
        # البحث عن التسجيل
        enrollment = StudentCourse.query.filter_by(
            student_id=student_id, 
            course_id=course_id
        ).first()
        
        if not enrollment:
            return jsonify({
                'success': False,
                'message': 'Student is not enrolled in this course'
            }), 404
        
        # إلغاء التسجيل
        db.session.delete(enrollment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Unenrolled from course successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error in unenroll_from_course: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/db-status', methods=['GET'])
def db_status():
    try:
        # التحقق من اتصال قاعدة البيانات
        db_connected = db.session.is_active
        
        # التحقق من وجود الجداول
        tables = {
            'User': User.query.count(),
            'Course': Course.query.count(),
            'StudentCourse': StudentCourse.query.count(),
            'Location': Location.query.count()
        }
        
        return jsonify({
            'success': True,
            'db_connected': db_connected,
            'tables': tables
        }), 200
    except Exception as e:
        logger.error(f"Error checking database status: {e}")
        return jsonify({
            'success': False,
            'message': f'Error checking database status: {str(e)}'
        }), 500

@app.route('/user', methods=['GET'])
def get_current_user():
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'message': 'Missing or invalid token'
            }), 401
        
        token = auth_header.split(' ')[1]
        
        # Verify token and get user ID
        # This is a simplified example - implement proper JWT verification
        # For example, using PyJWT library
        
        # For now, let's assume we can extract user_id from token
        # In a real app, you'd decode and verify the JWT token
        user_id = extract_user_id_from_token(token)
        
        if not user_id:
            return jsonify({
                'success': False,
                'message': 'Invalid token'
            }), 401
        
        # Get user from database
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        }), 200
    
    except Exception as e:
        logger.error(f"Error in get_current_user: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

def extract_user_id_from_token(token):
    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload.get('user_id')
    except pyjwt.ExpiredSignatureError:
        logger.error("Token expired")
        return None
    except pyjwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error extracting user ID from token: {e}")
        return None

@app.route('/courses/<int:course_id>/attendance', methods=['PUT'])
def update_attendance_state(course_id):
    try:
        data = request.get_json()
        max_retries = 5
        retry_count = 0
        retry_delay = 1  # seconds

        while retry_count < max_retries:
            try:
                # Use session.get() instead of query.get()
                course = db.session.get(Course, course_id)
                
                if not course:
                    return jsonify({
                        'success': False, 
                        'message': 'Course not found'
                    }), 404

                # Set the new attendance state
                new_state = data.get('isAttendanceOpen', False)
                course.isAttendanceOpen = new_state
                
                # Use a shorter transaction
                db.session.begin_nested()
                db.session.commit()
                
                # Double-check the change was saved
                db.session.refresh(course)
                
                if course.isAttendanceOpen == new_state:
                    return jsonify({
                        'success': True,
                        'message': 'Attendance state updated successfully',
                        'isAttendanceOpen': course.isAttendanceOpen
                    })
                else:
                    raise Exception("Failed to verify state change")
                
            except Exception as inner_error:
                retry_count += 1
                db.session.rollback()
                
                if retry_count >= max_retries:
                    logger.error(f"Failed after {max_retries} attempts: {inner_error}")
                    raise
                
                logger.warning(f"Retry {retry_count}/{max_retries} after error: {inner_error}")
                time.sleep(retry_delay)
                
    except Exception as e:
        logger.error(f"Error updating attendance state: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth's radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    
    return distance

@app.route('/attendance/verify-location', methods=['POST'])
def verify_location():
    try:
        data = request.get_json()
        logger.info(f"Received location data: {data}")  # Add logging
        
        # Get student location from request
        try:
            student_lat = float(data.get('latitude'))
            student_lon = float(data.get('longitude'))
            student_id = data.get('student_id')
            course_id = data.get('course_id')
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing student location: {e}")
            return jsonify({
                'success': False,
                'message': 'Invalid student location format'
            }), 400

        # Get course from database
        course = db.session.get(Course, course_id)
        if not course:
            return jsonify({
                'success': False,
                'message': 'Course not found'
            }), 404

        # Parse course location
        try:
            if not course.location or ',' not in course.location:
                return jsonify({
                    'success': False,
                    'message': 'Course location not set'
                }), 400

            course_location = course.location.split(',')
            if len(course_location) != 2:
                return jsonify({
                    'success': False,
                    'message': 'Invalid course location format'
                }), 400

            course_lat = float(course_location[0].strip())
            course_lon = float(course_location[1].strip())
        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing course location: {e}")
            return jsonify({
                'success': False,
                'message': f'Invalid course location format: {e}'
            }), 400

        # Calculate distance
        distance = calculate_distance(
            student_lat, student_lon,
            course_lat, course_lon
        )

        logger.info(f"Calculated distance: {distance}m")

        # Check if within range (30 meters)
        if distance <= 30:
            # Save the attendance record
            attendance = StudentLocation(
                student_id=student_id,
                course_id=course_id,
                latitude=student_lat,
                longitude=student_lon
            )
            db.session.add(attendance)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Attendance recorded successfully',
                'distance': distance
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Too far from class location ({distance:.1f}m)',
                'distance': distance
            })

    except Exception as e:
        logger.error(f"Error verifying location: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/attendance/verify', methods=['POST'])
def verify_attendance():
    data = request.get_json()
    student_id = data.get('student_id')
    course_id = data.get('course_id')

    # Verify GPS and face recognition
    # Add your logic here...

    return jsonify({'success': True, 'message': 'Attendance verified successfully'})

@app.route('/face/check-registration/<int:student_id>', methods=['GET'])
def check_face_registration(student_id):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'isRegistered': False, 'message': 'Student not found'}), 404

    if student.face_registered:
        return jsonify({'isRegistered': True})
    else:
        return jsonify({'isRegistered': False})

@app.route('/attendance/send-to-doctor', methods=['POST'])
def send_attendance_to_doctor():
    data = request.get_json()
    course_id = data.get('course_id')

    # Fetch attendance data and send to the doctor
    # Add your logic here...

    return jsonify({'success': True, 'message': 'Attendance sent to the doctor'})

def cleanup_database():
    try:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
    except Exception as e:
        logger.error(f"Error during database cleanup: {e}")

def kill_database_connections():
    try:
        # Force close all database connections
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        time.sleep(1)  # Give connections time to close
    except Exception as e:
        logger.error(f"Error killing database connections: {e}")

if __name__ == '__main__':
    try:
        # Kill existing connections first
        kill_database_connections()
        
        # Initialize database (only creates tables if they don't exist)
        with app.app_context():
            db.create_all()
            logger.info("Database initialized successfully")

        # Run the application
        app.run(host='0.0.0.0', debug=True, port=5000)

    except Exception as e:
        logger.error(f"Application error: {e}")
        raise
