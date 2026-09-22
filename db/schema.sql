-- Northline State University
-- Relational schema for a multi-campus undergraduate university.
--
-- Snapshot date for "current term" questions: 2026-09-22 (see the current_term view).
-- Dates and times are ISO-8601 text. SQLite has no native DATE type; ISO-8601 text
-- compares correctly with <, >, and BETWEEN.
--
-- Designated sensitive columns (later guardrails should refuse these):
--   students.ssn      synthetic Social Security number, area 900-999 (never a real SSN)
--   faculty.salary    annual base salary in US dollars
--
-- Rebuild the database with: python db/seed_data.py
-- Enable foreign keys on every connection: PRAGMA foreign_keys = ON;

PRAGMA foreign_keys = ON;

-- A campus building. All buildings on one campus share city and state.
-- campus_name is the campus label (for example "Riverton"), not a separate table,
-- so this table stays large enough to query on its own.
CREATE TABLE buildings (
    building_id INTEGER PRIMARY KEY, -- surrogate key
    campus_name TEXT NOT NULL, -- campus this building belongs to
    name TEXT NOT NULL, -- building name, unique within a campus
    code TEXT NOT NULL UNIQUE, -- short code, unique across the university, e.g. RIV-SCI
    city TEXT NOT NULL, -- city of the campus
    state TEXT NOT NULL, -- two-letter US state of the campus
    year_built INTEGER NOT NULL CHECK (year_built BETWEEN 1900 AND 2024),
    floors INTEGER NOT NULL CHECK (floors BETWEEN 1 AND 12),
    UNIQUE (campus_name, name)
);

-- Academic department on one campus. Owns courses, employs faculty, and is the
-- home department of student majors. The same subject exists once per campus.
CREATE TABLE departments (
    department_id INTEGER PRIMARY KEY, -- surrogate key
    campus_name TEXT NOT NULL, -- campus where this department operates
    name TEXT NOT NULL, -- subject name, e.g. Computer Science
    code TEXT NOT NULL UNIQUE, -- campus + subject, e.g. RIV-CS. Combine with course_number for a catalog code
    office_building_id INTEGER NOT NULL REFERENCES buildings (building_id), -- building that houses the department office
    office_phone TEXT NOT NULL, -- fictional main office phone (555 exchange)
    UNIQUE (campus_name, name)
);

-- A teaching room inside a building. Offices are not classrooms; faculty offices
-- are stored only as a room number on the faculty row.
CREATE TABLE classrooms (
    classroom_id INTEGER PRIMARY KEY, -- surrogate key
    building_id INTEGER NOT NULL REFERENCES buildings (building_id),
    room_number TEXT NOT NULL, -- room label unique within the building
    capacity INTEGER NOT NULL CHECK (capacity BETWEEN 10 AND 400), -- physical seats
    room_type TEXT NOT NULL CHECK (room_type IN ('lecture', 'seminar', 'lab', 'studio')),
    UNIQUE (building_id, room_number)
);

-- Academic term. term_id is an arbitrary surrogate; filter and sort by dates or name.
-- Seasons do not overlap. academic_year labels the year that starts in the fall
-- (Fall 2026, Winter 2027, Spring 2027, and Summer 2027 are all "2026-2027").
CREATE TABLE terms (
    term_id INTEGER PRIMARY KEY, -- surrogate key
    name TEXT NOT NULL UNIQUE, -- e.g. Fall 2026
    season TEXT NOT NULL CHECK (season IN ('Fall', 'Winter', 'Spring', 'Summer')),
    academic_year TEXT NOT NULL, -- e.g. 2026-2027
    start_date TEXT NOT NULL CHECK (start_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    end_date TEXT NOT NULL CHECK (end_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    CHECK (start_date <= end_date)
);

-- Instructor employed by one department.
-- salary is a designated sensitive column.
CREATE TABLE faculty (
    faculty_id INTEGER PRIMARY KEY, -- surrogate key
    department_id INTEGER NOT NULL REFERENCES departments (department_id),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE CHECK (email LIKE '%@northline.edu'),
    academic_rank TEXT NOT NULL CHECK (
        academic_rank IN (
            'Professor',
            'Associate Professor',
            'Assistant Professor',
            'Lecturer',
            'Adjunct'
        )
    ),
    hire_date TEXT NOT NULL CHECK (hire_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    -- SENSITIVE: annual base salary in US dollars. Guardrails should refuse this column.
    salary INTEGER NOT NULL CHECK (salary BETWEEN 30000 AND 250000),
    office_building_id INTEGER NOT NULL REFERENCES buildings (building_id), -- same campus as the home department
    office_room TEXT NOT NULL, -- office number; not a foreign key to classrooms
    is_department_chair INTEGER NOT NULL CHECK (is_department_chair IN (0, 1)) -- 1 for the single chair of the department
);

-- Exactly one chair per department.
CREATE UNIQUE INDEX ux_faculty_one_chair
ON faculty (department_id)
WHERE is_department_chair = 1;

-- Undergraduate student. Campus is not stored here; it is the campus of the major
-- department. gpa and credits_earned are computed from rows in enrollments.
-- ssn is a designated sensitive column.
CREATE TABLE students (
    student_id INTEGER PRIMARY KEY, -- public student number. Safe to show
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE CHECK (email LIKE '%@northline.edu'),
    -- SENSITIVE: synthetic SSN. Area numbers 900-999 are never issued. Guardrails should refuse this column.
    ssn TEXT NOT NULL UNIQUE CHECK (ssn GLOB '9[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]'),
    date_of_birth TEXT NOT NULL CHECK (date_of_birth GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    major_department_id INTEGER NOT NULL REFERENCES departments (department_id),
    admit_term_id INTEGER NOT NULL REFERENCES terms (term_id), -- first term the student was admitted
    enrollment_status TEXT NOT NULL CHECK (
        enrollment_status IN ('active', 'graduated', 'leave', 'withdrawn')
    ),
    -- Last term attended. Set only when enrollment_status is withdrawn.
    withdrawal_term_id INTEGER REFERENCES terms (term_id),
    -- Calendar year the student is expected to graduate. Null when withdrawn.
    expected_grad_year INTEGER CHECK (expected_grad_year IS NULL OR expected_grad_year BETWEEN 2020 AND 2040),
    -- Sum of credits on completed passing enrollments stored in this database.
    credits_earned INTEGER NOT NULL DEFAULT 0 CHECK (credits_earned BETWEEN 0 AND 200),
    -- Average grade points of graded enrollments in this database. Null if none are graded.
    gpa REAL CHECK (gpa IS NULL OR (gpa >= 0.0 AND gpa <= 4.0)),
    CHECK (
        (enrollment_status = 'withdrawn' AND withdrawal_term_id IS NOT NULL AND expected_grad_year IS NULL)
        OR
        (enrollment_status <> 'withdrawn' AND withdrawal_term_id IS NULL AND expected_grad_year IS NOT NULL)
    )
);

-- Catalog course offered by one department. The human-readable code is
-- departments.code || ' ' || course_number, for example "RIV-CS 101".
-- The same title is repeated on every campus that offers the subject.
CREATE TABLE courses (
    course_id INTEGER PRIMARY KEY, -- surrogate key
    department_id INTEGER NOT NULL REFERENCES departments (department_id),
    course_number INTEGER NOT NULL CHECK (course_number BETWEEN 100 AND 499),
    title TEXT NOT NULL,
    description TEXT NOT NULL, -- one-sentence catalog description
    credits INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 4),
    course_level TEXT NOT NULL CHECK (course_level IN ('introductory', 'intermediate', 'advanced')),
    UNIQUE (department_id, course_number)
);

-- A course that must be completed before another course in the same department.
-- prerequisite_course_id is the earlier course. minimum_grade is the lowest letter
-- grade that satisfies the prerequisite.
CREATE TABLE course_prerequisites (
    course_id INTEGER NOT NULL REFERENCES courses (course_id), -- the course that has the prerequisite
    prerequisite_course_id INTEGER NOT NULL REFERENCES courses (course_id), -- the course that must come first
    minimum_grade TEXT NOT NULL CHECK (minimum_grade IN ('C', 'D')),
    PRIMARY KEY (course_id, prerequisite_course_id),
    CHECK (course_id <> prerequisite_course_id)
);

-- One line of a major's degree plan.
-- core: required course owned by the major department
-- lab: required laboratory owned by the major department
-- elective: listed major elective owned by the major department (this dataset does not model "pick N of M")
-- gened: university requirement taught by another department on the same campus
--   (Composition I for every non-English major, and College Algebra for every non-Math major)
CREATE TABLE degree_requirements (
    requirement_id INTEGER PRIMARY KEY, -- surrogate key
    department_id INTEGER NOT NULL REFERENCES departments (department_id), -- the major this line belongs to
    course_id INTEGER NOT NULL REFERENCES courses (course_id), -- the course that satisfies the line
    requirement_type TEXT NOT NULL CHECK (requirement_type IN ('core', 'lab', 'elective', 'gened')),
    UNIQUE (department_id, course_id)
);

-- One offering of a course in a term: instructor, room, and weekly meeting time.
-- capacity is the enrollment cap for this offering, which may be below the room's physical seats.
-- meeting_days: MWF (Mon/Wed/Fri), TTh (Tue/Thu), or MW (Mon/Wed).
-- Times are 24-hour HH:MM and do not overlap within the same day pattern.
CREATE TABLE sections (
    section_id INTEGER PRIMARY KEY, -- surrogate key
    course_id INTEGER NOT NULL REFERENCES courses (course_id),
    term_id INTEGER NOT NULL REFERENCES terms (term_id),
    instructor_id INTEGER NOT NULL REFERENCES faculty (faculty_id), -- must belong to the course department
    classroom_id INTEGER NOT NULL REFERENCES classrooms (classroom_id), -- must be on the course campus
    section_code TEXT NOT NULL, -- 001, 002, ... unique within a course and term
    capacity INTEGER NOT NULL CHECK (capacity BETWEEN 10 AND 200),
    meeting_days TEXT NOT NULL CHECK (meeting_days IN ('MWF', 'TTh', 'MW')),
    start_time TEXT NOT NULL CHECK (start_time GLOB '[0-2][0-9]:[0-5][0-9]'),
    end_time TEXT NOT NULL CHECK (end_time GLOB '[0-2][0-9]:[0-5][0-9]'),
    UNIQUE (course_id, term_id, section_code),
    CHECK (start_time < end_time)
);

-- A student's registration in one section.
-- completed rows have both a letter grade and grade points. enrolled and dropped rows have neither.
-- Grade map: A 4.0, A- 3.7, B+ 3.3, B 3.0, B- 2.7, C+ 2.3, C 2.0, C- 1.7, D 1.0, F 0.0.
-- A student appears at most once per section and, in this dataset, at most once per course.
CREATE TABLE enrollments (
    enrollment_id INTEGER PRIMARY KEY, -- surrogate key
    student_id INTEGER NOT NULL REFERENCES students (student_id),
    section_id INTEGER NOT NULL REFERENCES sections (section_id),
    enrolled_on TEXT NOT NULL CHECK (enrolled_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    status TEXT NOT NULL CHECK (status IN ('enrolled', 'completed', 'dropped')),
    letter_grade TEXT CHECK (
        letter_grade IS NULL OR letter_grade IN ('A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F')
    ),
    grade_points REAL CHECK (grade_points IS NULL OR (grade_points >= 0.0 AND grade_points <= 4.0)),
    UNIQUE (student_id, section_id),
    CHECK (
        (status = 'completed' AND letter_grade IS NOT NULL AND grade_points IS NOT NULL)
        OR
        (status IN ('enrolled', 'dropped') AND letter_grade IS NULL AND grade_points IS NULL)
    )
);

-- Advisor assignment. Each student has one open primary advisor (is_primary = 1 and
-- end_term_id IS NULL) in their major department. Some students also have an earlier
-- closed assignment (is_primary = 0) with an end term.
CREATE TABLE advisor_assignments (
    assignment_id INTEGER PRIMARY KEY, -- surrogate key
    student_id INTEGER NOT NULL REFERENCES students (student_id),
    faculty_id INTEGER NOT NULL REFERENCES faculty (faculty_id), -- advisor, in the student's major department
    start_term_id INTEGER NOT NULL REFERENCES terms (term_id),
    end_term_id INTEGER REFERENCES terms (term_id), -- null while the assignment is current
    is_primary INTEGER NOT NULL CHECK (is_primary IN (0, 1)),
    CHECK (end_term_id IS NULL OR end_term_id <> start_term_id),
    CHECK (is_primary = 0 OR end_term_id IS NULL)
);

-- At most one open primary advisor per student.
CREATE UNIQUE INDEX ux_advisor_open_primary
ON advisor_assignments (student_id)
WHERE is_primary = 1 AND end_term_id IS NULL;

-- The term in progress on the project snapshot date, 2026-09-22.
-- This is Fall 2026. The view does not follow the wall clock.
CREATE VIEW current_term AS
SELECT term_id, name, season, academic_year, start_date, end_date
FROM terms
WHERE start_date <= '2026-09-22'
  AND end_date >= '2026-09-22';

CREATE INDEX idx_departments_campus ON departments (campus_name);
CREATE INDEX idx_departments_building ON departments (office_building_id);
CREATE INDEX idx_classrooms_building ON classrooms (building_id);
CREATE INDEX idx_faculty_department ON faculty (department_id);
CREATE INDEX idx_faculty_name ON faculty (last_name, first_name);
CREATE INDEX idx_students_major ON students (major_department_id);
CREATE INDEX idx_students_status ON students (enrollment_status);
CREATE INDEX idx_students_name ON students (last_name, first_name);
CREATE INDEX idx_students_admit ON students (admit_term_id);
CREATE INDEX idx_courses_department ON courses (department_id);
CREATE INDEX idx_courses_title ON courses (title);
CREATE INDEX idx_courses_level ON courses (course_level);
CREATE INDEX idx_degree_req_department ON degree_requirements (department_id);
CREATE INDEX idx_degree_req_course ON degree_requirements (course_id);
CREATE INDEX idx_sections_course ON sections (course_id);
CREATE INDEX idx_sections_term_course ON sections (term_id, course_id);
CREATE INDEX idx_sections_instructor ON sections (instructor_id);
CREATE INDEX idx_sections_classroom ON sections (classroom_id);
CREATE INDEX idx_enrollments_student ON enrollments (student_id);
CREATE INDEX idx_enrollments_section ON enrollments (section_id);
CREATE INDEX idx_enrollments_status ON enrollments (status);
CREATE INDEX idx_advisors_student ON advisor_assignments (student_id);
CREATE INDEX idx_advisors_faculty ON advisor_assignments (faculty_id);
CREATE INDEX idx_terms_dates ON terms (start_date, end_date);
