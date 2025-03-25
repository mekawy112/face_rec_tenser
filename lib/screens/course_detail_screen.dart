import 'package:flutter/material.dart';
import 'package:locate_me/screens/attendance_options_screen.dart';

class CourseDetailScreen extends StatelessWidget {
  final Map<String, dynamic> course;
  final Map<String, dynamic> studentData;

  const CourseDetailScreen({
    Key? key,
    required this.course,
    required this.studentData,
  }) : super(key: key);

  bool get isStudent => studentData['role'] == 'student';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(course['name'] ?? 'Course Details'),
        backgroundColor: Colors.blue.shade800,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Course Code: ${course['code']}',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                        'Description: ${course['description'] ?? 'No description'}'),
                    Text('Day: ${course['day'] ?? 'N/A'}'),
                    Text('Time: ${course['time'] ?? 'N/A'}'),
                    Text('Location: ${course['location'] ?? 'N/A'}'),
                    const SizedBox(height: 16),

                    // Show attendance button only for students when attendance is open
                    if (isStudent && course['isAttendanceOpen'] == true)
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          onPressed: () {
                            // Navigate to AttendanceOptionsScreen with required parameters
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (context) => AttendanceOptionsScreen(
                                  courseData: course,
                                  studentData: studentData,
                                ),
                              ),
                            );
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.green,
                            padding: const EdgeInsets.symmetric(vertical: 12),
                          ),
                          child: const Text(
                            'Take Attendance',
                            style: TextStyle(
                              fontSize: 16,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),

                    // Show message if attendance is closed
                    if (isStudent && course['isAttendanceOpen'] != true)
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        color: Colors.red.shade100,
                        child: const Text(
                          'Attendance is currently closed',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: Colors.red,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
