"""Build db/university.db from schema.sql.

The generator is deterministic (random seed 42) and uses only the Python
standard library. Running it deletes and recreates the SQLite file.

    python db/seed_data.py
"""

from __future__ import annotations

import random
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import AS_OF_DATE, DB_PATH, SCHEMA_PATH, UNIVERSITY_NAME

AS_OF = date.fromisoformat(AS_OF_DATE)
SEED = 42

# Terms that receive class sections. Earlier terms exist only as history.
SECTION_WINDOW_START = date(2023, 8, 1)
SECTION_WINDOW_END = date(2027, 2, 1)

CAMPUSES = [
    ("Riverton", "Riverton", "IL", "RIV"),
    ("Lakeshore", "Lakeshore", "WI", "LAK"),
    ("Pine Ridge", "Pine Ridge", "CO", "PIN"),
    ("Harborview", "Harborview", "WA", "HAR"),
    ("Red Mesa", "Red Mesa", "AZ", "RED"),
    ("Cedar Falls", "Cedar Falls", "IA", "CED"),
    ("Easton", "Easton", "PA", "EAS"),
    ("Westfield", "Westfield", "MA", "WES"),
]

BUILDINGS = [
    ("Science Center", "SCI"),
    ("Engineering Building", "ENGR"),
    ("Mathematics Building", "MATH"),
    ("Humanities Hall", "HUM"),
    ("Business School", "BUSI"),
    ("Nursing Pavilion", "NURS"),
    ("Arts Building", "ARTS"),
    ("Library", "LIB"),
    ("Student Union", "UNION"),
    ("Lecture Center", "LECT"),
    ("Laboratory Annex", "LABS"),
    ("Graduate Studies Building", "GRAD"),
    ("Administration Building", "ADMIN"),
    ("Recreation Center", "RECR"),
    ("Auditorium", "AUD"),
]

DEPT_BUILDING = {
    "Physics": "SCI",
    "Chemistry": "SCI",
    "Biology": "SCI",
    "Mechanical Engineering": "ENGR",
    "Electrical Engineering": "ENGR",
    "Mathematics": "MATH",
    "Computer Science": "MATH",
    "English": "HUM",
    "History": "HUM",
    "Sociology": "HUM",
    "Psychology": "HUM",
    "Business Administration": "BUSI",
    "Economics": "BUSI",
    "Nursing": "NURS",
    "Art": "ARTS",
}

DEPT_ABBREV = {
    "Computer Science": "CS",
    "Mathematics": "MATH",
    "Physics": "PHYS",
    "Chemistry": "CHEM",
    "Biology": "BIO",
    "Psychology": "PSY",
    "English": "ENGL",
    "History": "HIST",
    "Economics": "ECON",
    "Business Administration": "BUS",
    "Mechanical Engineering": "ME",
    "Electrical Engineering": "EE",
    "Nursing": "NURS",
    "Sociology": "SOC",
    "Art": "ART",
}

DEPT_NAMES = list(DEPT_ABBREV)
POPULAR = {
    "Computer Science",
    "Business Administration",
    "Nursing",
    "Psychology",
    "Biology",
}

# (room_number, capacity, room_type) four times per building.
ROOM_TEMPLATES = {
    "LECT": [("100", 120, "lecture"), ("110", 90, "lecture"), ("120", 72, "lecture"), ("130", 48, "lecture")],
    "AUD": [("1", 180, "lecture"), ("2", 80, "lecture"), ("3", 40, "seminar"), ("4", 30, "seminar")],
    "LABS": [("101", 24, "lab"), ("102", 24, "lab"), ("103", 22, "lab"), ("104", 20, "lab")],
    "SCI": [("110", 24, "lab"), ("112", 24, "lab"), ("201", 32, "seminar"), ("202", 28, "seminar")],
    "ENGR": [("101", 24, "lab"), ("102", 24, "lab"), ("210", 36, "seminar"), ("220", 30, "seminar")],
    "NURS": [("101", 20, "lab"), ("102", 20, "lab"), ("201", 32, "seminar"), ("202", 28, "seminar")],
    "ARTS": [("101", 18, "studio"), ("102", 18, "studio"), ("201", 16, "studio"), ("202", 20, "studio")],
    "DEFAULT": [("101", 40, "seminar"), ("102", 32, "seminar"), ("201", 28, "seminar"), ("202", 24, "seminar")],
}

# course_number -> (title, credits, level, topic)
CATALOG = {
    "Computer Science": [
        (101, "Introduction to Programming", 4, "introductory", "variables, control flow, functions, and testing"),
        (201, "Data Structures", 4, "intermediate", "lists, trees, hash tables, and algorithm complexity"),
        (301, "Design of Algorithms", 3, "advanced", "divide and conquer, graph algorithms, and dynamic programming"),
        (401, "Operating Systems", 3, "advanced", "processes, memory, file systems, and concurrency"),
    ],
    "Mathematics": [
        (101, "College Algebra and Functions", 4, "introductory", "functions, equations, and exponential models"),
        (201, "Calculus I", 4, "intermediate", "limits, derivatives, and basic applications"),
        (301, "Calculus II", 3, "advanced", "integration techniques, sequences, and series"),
        (401, "Linear Algebra", 3, "advanced", "vector spaces, matrices, and eigenvalues"),
    ],
    "Physics": [
        (101, "Introductory Physics", 4, "introductory", "motion, forces, energy, and momentum"),
        (201, "Mechanics", 4, "intermediate", "Newtonian mechanics and rotational motion"),
        (301, "Electricity and Magnetism", 3, "advanced", "fields, circuits, and electromagnetic waves"),
        (401, "Quantum Physics", 3, "advanced", "wave functions and simple quantum systems"),
    ],
    "Chemistry": [
        (101, "General Chemistry", 4, "introductory", "atoms, bonding, stoichiometry, and reactions"),
        (201, "Organic Chemistry", 4, "intermediate", "structure and reactions of carbon compounds"),
        (301, "Analytical Chemistry", 3, "advanced", "quantitative measurement and instrumentation"),
        (401, "Physical Chemistry", 3, "advanced", "thermodynamics and chemical kinetics"),
    ],
    "Biology": [
        (101, "General Biology", 4, "introductory", "cells, genetics, evolution, and ecology"),
        (201, "Genetics", 4, "intermediate", "inheritance, molecular genetics, and variation"),
        (301, "Cell Biology", 3, "advanced", "organelles, membranes, and cell signaling"),
        (401, "Ecology", 3, "advanced", "populations, communities, and ecosystems"),
    ],
    "Psychology": [
        (101, "Introduction to Psychology", 3, "introductory", "behavior, cognition, and research in psychology"),
        (201, "Research Methods", 4, "intermediate", "study design, measurement, and basic statistics"),
        (301, "Cognitive Psychology", 3, "advanced", "attention, memory, and problem solving"),
        (401, "Abnormal Psychology", 3, "advanced", "classification and treatment of psychological disorders"),
    ],
    "English": [
        (101, "Composition I", 3, "introductory", "academic writing, argument, and revision"),
        (201, "Composition II", 3, "intermediate", "research writing and rhetorical analysis"),
        (301, "American Literature", 3, "advanced", "major works and periods of American literature"),
        (401, "Shakespeare", 3, "advanced", "selected plays and their dramatic contexts"),
    ],
    "History": [
        (101, "World History", 3, "introductory", "global societies from the early modern period onward"),
        (201, "United States History", 3, "intermediate", "political and social history of the United States"),
        (301, "Historical Methods", 3, "advanced", "sourcing, interpretation, and historiography"),
        (401, "Seminar in History", 3, "advanced", "a research seminar on a rotating historical theme"),
    ],
    "Economics": [
        (101, "Principles of Microeconomics", 3, "introductory", "supply, demand, and market behavior"),
        (201, "Principles of Macroeconomics", 3, "intermediate", "inflation, employment, and national income"),
        (301, "Intermediate Microeconomics", 3, "advanced", "consumer theory and market structure"),
        (401, "Econometrics", 3, "advanced", "regression methods for economic data"),
    ],
    "Business Administration": [
        (101, "Introduction to Business", 3, "introductory", "firms, markets, and basic management"),
        (201, "Financial Accounting", 3, "intermediate", "the accounting cycle and financial statements"),
        (301, "Marketing Principles", 3, "advanced", "segmentation, pricing, and promotion"),
        (401, "Strategic Management", 3, "advanced", "competitive strategy and case analysis"),
    ],
    "Mechanical Engineering": [
        (101, "Introduction to Engineering Design", 3, "introductory", "design process, teamwork, and technical communication"),
        (201, "Statics", 4, "intermediate", "forces, moments, and equilibrium of rigid bodies"),
        (301, "Thermodynamics", 3, "advanced", "energy, heat, and the laws of thermodynamics"),
        (401, "Machine Design", 3, "advanced", "sizing common machine components"),
    ],
    "Electrical Engineering": [
        (101, "Introduction to Electrical Engineering", 3, "introductory", "charge, current, and basic circuit elements"),
        (201, "Circuit Analysis", 4, "intermediate", "resistive and dynamic circuits"),
        (301, "Signals and Systems", 3, "advanced", "linear systems and transforms"),
        (401, "Digital Systems", 3, "advanced", "combinational and sequential logic"),
    ],
    "Nursing": [
        (101, "Foundations of Nursing", 4, "introductory", "the nursing process and professional standards"),
        (201, "Health Assessment", 4, "intermediate", "history taking and physical assessment"),
        (301, "Adult Health Nursing", 3, "advanced", "care of adults with common medical conditions"),
        (401, "Community Health Nursing", 3, "advanced", "public health and population-focused care"),
    ],
    "Sociology": [
        (101, "Introduction to Sociology", 3, "introductory", "social structure, culture, and inequality"),
        (201, "Social Problems", 3, "intermediate", "contemporary social problems and policy responses"),
        (301, "Research Methods in Sociology", 3, "advanced", "surveys, fieldwork, and research ethics"),
        (401, "Social Theory", 3, "advanced", "classical and contemporary social theory"),
    ],
    "Art": [
        (101, "Drawing I", 3, "introductory", "observational drawing and composition"),
        (201, "Art History Survey", 3, "intermediate", "major periods of Western and global art"),
        (301, "Painting", 3, "advanced", "materials and methods of painting"),
        (401, "Senior Studio", 3, "advanced", "a self-directed studio project"),
    ],
}

LABS = {
    "Computer Science": ("Programming Laboratory", "supervised practice writing and debugging programs"),
    "Physics": ("Physics Laboratory", "measurement, error analysis, and mechanics experiments"),
    "Chemistry": ("General Chemistry Laboratory", "laboratory technique and chemical safety"),
    "Biology": ("Biology Laboratory", "microscopy, dissection, and data collection"),
    "Mechanical Engineering": ("Engineering Design Laboratory", "prototyping and design reviews"),
    "Electrical Engineering": ("Circuits Laboratory", "building and measuring simple circuits"),
    "Nursing": ("Clinical Skills Laboratory", "basic clinical skills in a simulation setting"),
}

SALARY_BANDS = {
    "Professor": (132000, 186000),
    "Associate Professor": (96000, 128000),
    "Assistant Professor": (74000, 98000),
    "Lecturer": (54000, 76000),
    "Adjunct": (40000, 58000),
}
RANK_WEIGHTS = [
    ("Professor", 15),
    ("Associate Professor", 20),
    ("Assistant Professor", 25),
    ("Lecturer", 25),
    ("Adjunct", 15),
]

ADMIT_PLAN = [
    ("Fall 2022", 100),
    ("Spring 2023", 40),
    ("Fall 2023", 120),
    ("Spring 2024", 40),
    ("Fall 2024", 160),
    ("Spring 2025", 40),
    ("Fall 2025", 160),
    ("Spring 2026", 40),
    ("Fall 2026", 100),
]

GRADE_POINTS = {
    "A": 4.0,
    "A-": 3.7,
    "B+": 3.3,
    "B": 3.0,
    "B-": 2.7,
    "C+": 2.3,
    "C": 2.0,
    "C-": 1.7,
    "D": 1.0,
    "F": 0.0,
}
GRADE_BAG = (
    ["A"] * 30
    + ["A-"] * 10
    + ["B+"] * 10
    + ["B"] * 20
    + ["B-"] * 8
    + ["C+"] * 7
    + ["C"] * 8
    + ["C-"] * 3
    + ["D"] * 2
    + ["F"] * 2
)

SLOTS = [
    ("MWF", "08:00", "08:50"),
    ("MWF", "09:00", "09:50"),
    ("MWF", "10:00", "10:50"),
    ("MWF", "11:00", "11:50"),
    ("MWF", "13:00", "13:50"),
    ("MWF", "14:00", "14:50"),
    ("MWF", "15:00", "15:50"),
    ("TTh", "08:00", "09:15"),
    ("TTh", "09:30", "10:45"),
    ("TTh", "11:00", "12:15"),
    ("TTh", "13:00", "14:15"),
    ("TTh", "14:30", "15:45"),
    ("TTh", "16:00", "17:15"),
    ("MW", "16:00", "17:15"),
]

FIRST_NAMES = """
James Mary Robert Patricia John Jennifer Michael Linda David Elizabeth
William Barbara Richard Susan Joseph Jessica Thomas Sarah Charles Karen
Christopher Nancy Daniel Lisa Matthew Betty Anthony Margaret Mark Sandra
Donald Ashley Steven Kimberly Paul Emily Andrew Donna Joshua Michelle
Kenneth Dorothy Kevin Carol Brian Amanda George Melissa Timothy Deborah
Ronald Stephanie Edward Rebecca Jason Sharon Jeffrey Laura Ryan Cynthia
Jacob Kathleen Gary Amy Nicholas Angela Eric Shirley Jonathan Anna
Stephen Brenda Larry Pamela Justin Emma Scott Nicole Brandon Helen
Benjamin Samantha Samuel Katherine Raymond Christine Gregory Debra
Frank Rachel Alexander Carolyn Patrick Janet Jack Catherine Dennis Maria
Jerry Heather Tyler Diane Aaron Ruth Jose Olivia Adam Julie Nathan Joyce
Henry Virginia Douglas Victoria Zachary Kelly Peter Lauren Kyle Christina
""".split()

LAST_NAMES = """
Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez
Hernandez Lopez Gonzalez Wilson Anderson Thomas Taylor Moore Jackson Martin
Lee Perez Thompson White Harris Sanchez Clark Ramirez Lewis Robinson Walker
Young Allen King Wright Scott Torres Nguyen Hill Flores Green Adams Nelson
Baker Hall Rivera Campbell Mitchell Carter Roberts Gomez Phillips Evans
Turner Diaz Parker Cruz Edwards Collins Reyes Stewart Morris Morales Murphy
Cook Rogers Gutierrez Ortiz Morgan Cooper Peterson Bailey Reed Kelly Howard
Ramos Kim Cox Ward Richardson Watson Brooks Chavez Wood Bennett Gray Mendoza
Ruiz Hughes Price Alvarez Castillo Sanders Patel Myers Long Ross Foster
""".split()

EXPECTED_COUNTS = {
    "buildings": 120,
    "departments": 120,
    "classrooms": 480,
    "terms": 100,
    "faculty": 400,
    "students": 800,
    "courses": 536,
    "course_prerequisites": 416,
    "degree_requirements": 760,
    "sections": 800,
    "enrollments": 1000,
    "advisor_assignments": 900,
}


@dataclass
class Term:
    term_id: int
    name: str
    season: str
    academic_year: str
    start_date: date
    end_date: date

    def row(self) -> tuple:
        return (
            self.term_id,
            self.name,
            self.season,
            self.academic_year,
            self.start_date.isoformat(),
            self.end_date.isoformat(),
        )


@dataclass
class Building:
    building_id: int
    campus_name: str
    name: str
    code: str
    city: str
    state: str
    year_built: int
    floors: int

    def row(self) -> tuple:
        return (
            self.building_id,
            self.campus_name,
            self.name,
            self.code,
            self.city,
            self.state,
            self.year_built,
            self.floors,
        )


@dataclass
class Department:
    department_id: int
    campus_name: str
    name: str
    code: str
    office_building_id: int
    office_phone: str

    def row(self) -> tuple:
        return (
            self.department_id,
            self.campus_name,
            self.name,
            self.code,
            self.office_building_id,
            self.office_phone,
        )


@dataclass
class Classroom:
    classroom_id: int
    building_id: int
    room_number: str
    capacity: int
    room_type: str
    campus_name: str

    def row(self) -> tuple:
        return (self.classroom_id, self.building_id, self.room_number, self.capacity, self.room_type)


@dataclass
class Faculty:
    faculty_id: int
    department_id: int
    first_name: str
    last_name: str
    email: str
    academic_rank: str
    hire_date: date
    salary: int
    office_building_id: int
    office_room: str
    is_department_chair: int = 0

    def row(self) -> tuple:
        return (
            self.faculty_id,
            self.department_id,
            self.first_name,
            self.last_name,
            self.email,
            self.academic_rank,
            self.hire_date.isoformat(),
            self.salary,
            self.office_building_id,
            self.office_room,
            self.is_department_chair,
        )


@dataclass
class Student:
    student_id: int
    first_name: str
    last_name: str
    email: str
    ssn: str
    date_of_birth: date
    major_department_id: int
    admit_term: Term
    enrollment_status: str
    withdrawal_term: Term | None
    expected_grad_year: int | None
    campus_name: str
    credits_earned: int = 0
    gpa: float | None = None

    def row(self) -> tuple:
        return (
            self.student_id,
            self.first_name,
            self.last_name,
            self.email,
            self.ssn,
            self.date_of_birth.isoformat(),
            self.major_department_id,
            self.admit_term.term_id,
            self.enrollment_status,
            None if self.withdrawal_term is None else self.withdrawal_term.term_id,
            self.expected_grad_year,
            self.credits_earned,
            self.gpa,
        )


@dataclass
class Course:
    course_id: int
    department_id: int
    course_number: int
    title: str
    description: str
    credits: int
    course_level: str
    campus_name: str
    department_name: str

    def row(self) -> tuple:
        return (
            self.course_id,
            self.department_id,
            self.course_number,
            self.title,
            self.description,
            self.credits,
            self.course_level,
        )


@dataclass
class Prerequisite:
    course_id: int
    prerequisite_course_id: int
    minimum_grade: str

    def row(self) -> tuple:
        return (self.course_id, self.prerequisite_course_id, self.minimum_grade)


@dataclass
class Requirement:
    requirement_id: int
    department_id: int
    course_id: int
    requirement_type: str

    def row(self) -> tuple:
        return (self.requirement_id, self.department_id, self.course_id, self.requirement_type)


@dataclass
class Section:
    section_id: int
    course_id: int
    term_id: int
    instructor_id: int
    classroom_id: int
    section_code: str
    capacity: int
    meeting_days: str
    start_time: str
    end_time: str
    campus_name: str
    department_id: int
    course_number: int

    def row(self) -> tuple:
        return (
            self.section_id,
            self.course_id,
            self.term_id,
            self.instructor_id,
            self.classroom_id,
            self.section_code,
            self.capacity,
            self.meeting_days,
            self.start_time,
            self.end_time,
        )


@dataclass
class Enrollment:
    enrollment_id: int
    student_id: int
    section_id: int
    enrolled_on: date
    status: str
    letter_grade: str | None
    grade_points: float | None

    def row(self) -> tuple:
        return (
            self.enrollment_id,
            self.student_id,
            self.section_id,
            self.enrolled_on.isoformat(),
            self.status,
            self.letter_grade,
            self.grade_points,
        )


@dataclass
class AdvisorAssignment:
    assignment_id: int
    student_id: int
    faculty_id: int
    start_term_id: int
    end_term_id: int | None
    is_primary: int

    def row(self) -> tuple:
        return (
            self.assignment_id,
            self.student_id,
            self.faculty_id,
            self.start_term_id,
            self.end_term_id,
            self.is_primary,
        )


def parse_days(meeting_days: str) -> set[str]:
    return {"MWF": {"M", "W", "F"}, "TTh": {"T", "Th"}, "MW": {"M", "W"}}[meeting_days]


def minutes(hhmm: str) -> int:
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def times_conflict(days_a: str, start_a: str, end_a: str, days_b: str, start_b: str, end_b: str) -> bool:
    if parse_days(days_a).isdisjoint(parse_days(days_b)):
        return False
    return minutes(start_a) < minutes(end_b) and minutes(start_b) < minutes(end_a)


def synthetic_ssn(n: int) -> str:
    """Build a unique fake SSN. Area 900-999 is never issued by the SSA."""
    area = 900 + ((n - 1) % 100)
    group = 10 + ((n - 1) // 100)
    serial = 1000 + n
    return f"{area:03d}-{group:02d}-{serial:04d}"


def person_email(first: str, last: str, role: str, person_id: int) -> str:
    return f"{first}.{last}.{role}{person_id}@northline.edu".lower()


def build_terms() -> list[Term]:
    terms: list[Term] = []
    term_id = 1
    for year in range(2002, 2027):
        academic_year = f"{year}-{year + 1}"
        spans = [
            ("Fall", date(year, 8, 25), date(year, 12, 12)),
            ("Winter", date(year + 1, 1, 5), date(year + 1, 1, 23)),
            ("Spring", date(year + 1, 2, 1), date(year + 1, 5, 15)),
            ("Summer", date(year + 1, 6, 8), date(year + 1, 7, 31)),
        ]
        for season, start, end in spans:
            terms.append(
                Term(term_id, f"{season} {start.year}", season, academic_year, start, end)
            )
            term_id += 1
    if len(terms) != 100:
        raise RuntimeError(f"expected 100 terms, got {len(terms)}")
    for earlier, later in zip(terms, terms[1:]):
        if earlier.end_date >= later.start_date:
            raise RuntimeError(f"overlapping terms {earlier.name} and {later.name}")
    current = [term.name for term in terms if term.start_date <= AS_OF <= term.end_date]
    if current != ["Fall 2026"]:
        raise RuntimeError(f"expected current term Fall 2026, got {current}")
    return terms


def build_places() -> tuple[list[Building], list[Department], list[Classroom]]:
    buildings: list[Building] = []
    departments: list[Department] = []
    classrooms: list[Classroom] = []
    building_id = 1
    department_id = 1
    classroom_id = 1
    building_ids: dict[tuple[str, str], int] = {}

    for campus_index, (campus, city, state, campus_code) in enumerate(CAMPUSES):
        for building_index, (building_name, building_code) in enumerate(BUILDINGS):
            floors = 2 if building_code in {"AUD", "RECR"} else 3 + (building_index % 4)
            year_built = 1948 + campus_index * 6 + building_index * 2
            buildings.append(
                Building(
                    building_id,
                    campus,
                    building_name,
                    f"{campus_code}-{building_code}",
                    city,
                    state,
                    year_built,
                    floors,
                )
            )
            building_ids[(campus, building_code)] = building_id
            template = ROOM_TEMPLATES.get(building_code, ROOM_TEMPLATES["DEFAULT"])
            for room_number, capacity, room_type in template:
                classrooms.append(
                    Classroom(
                        classroom_id,
                        building_id,
                        room_number,
                        capacity,
                        room_type,
                        campus,
                    )
                )
                classroom_id += 1
            building_id += 1

        for name in DEPT_NAMES:
            home = building_ids[(campus, DEPT_BUILDING[name])]
            departments.append(
                Department(
                    department_id,
                    campus,
                    name,
                    f"{campus_code}-{DEPT_ABBREV[name]}",
                    home,
                    f"(555) 201-{department_id:04d}",
                )
            )
            department_id += 1

    return buildings, departments, classrooms


def build_faculty(
    rng: random.Random,
    departments: list[Department],
) -> list[Faculty]:
    faculty: list[Faculty] = []
    next_room: dict[int, int] = defaultdict(lambda: 301)
    faculty_id = 1
    ranks = [rank for rank, weight in RANK_WEIGHTS for _ in range(weight)]
    grouped: dict[int, list[Faculty]] = defaultdict(list)

    for index, department in enumerate(departments):
        count = 4 if index % 3 == 0 else 3
        for _ in range(count):
            rank = rng.choice(ranks)
            low, high = SALARY_BANDS[rank]
            if rank == "Professor":
                hire_year = rng.randint(2004, 2012)
            elif rank == "Associate Professor":
                hire_year = rng.randint(2008, 2016)
            elif rank == "Assistant Professor":
                hire_year = rng.randint(2014, 2020)
            elif rank == "Lecturer":
                hire_year = rng.randint(2012, 2021)
            else:
                hire_year = rng.randint(2016, 2021)
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            room_number = str(next_room[department.office_building_id])
            next_room[department.office_building_id] += 1
            person = Faculty(
                faculty_id,
                department.department_id,
                first,
                last,
                person_email(first, last, "f", faculty_id),
                rank,
                date(hire_year, 8, 15),
                rng.randrange(low, high + 1, 1000),
                department.office_building_id,
                room_number,
            )
            faculty.append(person)
            grouped[department.department_id].append(person)
            faculty_id += 1

    for group in grouped.values():
        eligible = [person for person in group if person.academic_rank != "Adjunct"] or group
        rng.choice(eligible).is_department_chair = 1

    if len(faculty) != 400:
        raise RuntimeError(f"expected 400 faculty, got {len(faculty)}")
    return faculty


def assign_status(rng: random.Random, admit_name: str) -> str:
    if admit_name == "Fall 2026":
        return "active"
    if admit_name in {"Fall 2022", "Spring 2023"}:
        roll = rng.randrange(100)
        if roll < 70:
            return "graduated"
        if roll < 90:
            return "active"
        return "withdrawn"
    roll = rng.randrange(100)
    if roll < 86:
        return "active"
    if roll < 93:
        return "leave"
    return "withdrawn"


def build_students(
    rng: random.Random,
    departments: list[Department],
    terms: list[Term],
    section_terms: list[Term],
) -> list[Student]:
    by_name = {term.name: term for term in terms}
    pool: list[Term] = []
    for name, count in ADMIT_PLAN:
        pool.extend([by_name[name]] * count)
    if len(pool) != 800:
        raise RuntimeError(f"admit plan sums to {len(pool)}")
    rng.shuffle(pool)

    students: list[Student] = []
    student_id = 1
    pool_index = 0
    for department in departments:
        cohort_size = 12 if department.name in POPULAR else 4
        for _ in range(cohort_size):
            admit = pool[pool_index]
            pool_index += 1
            status = assign_status(rng, admit.name)
            withdrawal = None
            if status == "withdrawn":
                options = [
                    term
                    for term in section_terms
                    if term.start_date >= admit.start_date and term.end_date < AS_OF
                ]
                if not options:
                    raise RuntimeError(f"no withdrawal term for admit {admit.name}")
                withdrawal = rng.choice(options)
                expected = None
            elif status == "graduated":
                expected = 2026
            else:
                expected = admit.start_date.year + 4
            age = rng.randint(18, 23)
            born = date(admit.start_date.year - age, rng.randint(1, 12), rng.randint(1, 28))
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            students.append(
                Student(
                    student_id,
                    first,
                    last,
                    person_email(first, last, "s", student_id),
                    synthetic_ssn(student_id),
                    born,
                    department.department_id,
                    admit,
                    status,
                    withdrawal,
                    expected,
                    department.campus_name,
                )
            )
            student_id += 1
    if len(students) != 800:
        raise RuntimeError(f"expected 800 students, got {len(students)}")
    return students


def build_catalog(
    departments: list[Department],
) -> tuple[list[Course], list[Prerequisite], list[Requirement]]:
    courses: list[Course] = []
    prerequisites: list[Prerequisite] = []
    requirements: list[Requirement] = []
    course_id = 1
    by_key: dict[tuple[int, int], Course] = {}
    dept_by_campus_name = {(dept.campus_name, dept.name): dept for dept in departments}

    for department in departments:
        for number, title, credits, level, topic in CATALOG[department.name]:
            course = Course(
                course_id,
                department.department_id,
                number,
                title,
                f"{title} is an {level} course covering {topic}.",
                credits,
                level,
                department.campus_name,
                department.name,
            )
            courses.append(course)
            by_key[(department.department_id, number)] = course
            course_id += 1
        if department.name in LABS:
            title, topic = LABS[department.name]
            course = Course(
                course_id,
                department.department_id,
                110,
                title,
                f"{title} is an introductory course covering {topic}.",
                1,
                "introductory",
                department.campus_name,
                department.name,
            )
            courses.append(course)
            by_key[(department.department_id, 110)] = course
            course_id += 1

    chains = [(201, 101, "C"), (301, 201, "C"), (401, 301, "C"), (110, 101, "D")]
    for (department_id, number), course in by_key.items():
        for target, prior, minimum in chains:
            if number == target and (department_id, prior) in by_key:
                prerequisites.append(
                    Prerequisite(course.course_id, by_key[(department_id, prior)].course_id, minimum)
                )

    requirement_id = 1
    type_by_number = {101: "core", 201: "core", 301: "core", 401: "elective", 110: "lab"}
    for department in departments:
        for number, req_type in type_by_number.items():
            course = by_key.get((department.department_id, number))
            if course is None:
                continue
            requirements.append(
                Requirement(requirement_id, department.department_id, course.course_id, req_type)
            )
            requirement_id += 1
        if department.name != "English":
            english = dept_by_campus_name[(department.campus_name, "English")]
            writing = by_key[(english.department_id, 101)]
            requirements.append(
                Requirement(requirement_id, department.department_id, writing.course_id, "gened")
            )
            requirement_id += 1
        if department.name != "Mathematics":
            math = dept_by_campus_name[(department.campus_name, "Mathematics")]
            algebra = by_key[(math.department_id, 101)]
            requirements.append(
                Requirement(requirement_id, department.department_id, algebra.course_id, "gened")
            )
            requirement_id += 1

    return courses, prerequisites, requirements


class Scheduler:
    def __init__(
        self,
        rng: random.Random,
        faculty: list[Faculty],
        classrooms: list[Classroom],
        departments: list[Department],
    ) -> None:
        self.rng = rng
        self.departments = {dept.department_id: dept for dept in departments}
        self.faculty_by_dept: dict[int, list[Faculty]] = defaultdict(list)
        for person in faculty:
            self.faculty_by_dept[person.department_id].append(person)
        self.rooms_by_campus: dict[str, list[Classroom]] = defaultdict(list)
        for room in classrooms:
            self.rooms_by_campus[room.campus_name].append(room)
        self.faculty_busy: dict[tuple[int, int], list[tuple[str, str, str]]] = defaultdict(list)
        self.room_busy: dict[tuple[int, int], list[tuple[str, str, str]]] = defaultdict(list)
        self.faculty_load: dict[tuple[int, int], int] = defaultdict(int)
        self.section_seq: dict[tuple[int, int], int] = defaultdict(int)
        self.sections: list[Section] = []

    def add(self, course: Course, term: Term) -> bool:
        department = self.departments[course.department_id]
        instructors = [
            person
            for person in self.faculty_by_dept[course.department_id]
            if person.hire_date <= term.start_date
        ]
        rooms = self.rooms_by_campus[department.campus_name]
        if course.course_number == 110:
            prefer = "lab"
            target = 22
        elif department.name == "Art":
            prefer = "studio"
            target = 16
        elif course.course_number == 101:
            prefer = "lecture"
            target = 36
        else:
            prefer = "seminar"
            target = {201: 30, 301: 24, 401: 20}.get(course.course_number, 24)

        slot_order = list(SLOTS)
        self.rng.shuffle(slot_order)
        for slot in slot_order:
            available = [
                person
                for person in instructors
                if self.faculty_load[(person.faculty_id, term.term_id)] < 4
                and not self._busy(self.faculty_busy, (person.faculty_id, term.term_id), slot)
            ]
            room = self._choose_room(rooms, term.term_id, slot, prefer, target)
            if not available or room is None:
                continue
            instructor = self.rng.choice(available)
            self.faculty_busy[(instructor.faculty_id, term.term_id)].append(slot)
            self.room_busy[(room.classroom_id, term.term_id)].append(slot)
            self.faculty_load[(instructor.faculty_id, term.term_id)] += 1
            key = (course.course_id, term.term_id)
            self.section_seq[key] += 1
            self.sections.append(
                Section(
                    len(self.sections) + 1,
                    course.course_id,
                    term.term_id,
                    instructor.faculty_id,
                    room.classroom_id,
                    f"{self.section_seq[key]:03d}",
                    min(target, room.capacity),
                    slot[0],
                    slot[1],
                    slot[2],
                    department.campus_name,
                    course.department_id,
                    course.course_number,
                )
            )
            return True
        return False

    def _busy(
        self,
        store: dict[tuple[int, int], list[tuple[str, str, str]]],
        key: tuple[int, int],
        slot: tuple[str, str, str],
    ) -> bool:
        days, start, end = slot
        return any(
            times_conflict(days, start, end, other_days, other_start, other_end)
            for other_days, other_start, other_end in store.get(key, [])
        )

    def _choose_room(
        self,
        rooms: list[Classroom],
        term_id: int,
        slot: tuple[str, str, str],
        prefer: str,
        target: int,
    ) -> Classroom | None:
        free = [
            room
            for room in rooms
            if room.capacity >= 12 and not self._busy(self.room_busy, (room.classroom_id, term_id), slot)
        ]
        preferred = [room for room in free if room.room_type == prefer]
        if preferred:
            free = preferred
        if not free:
            return None
        big_enough = [room for room in free if room.capacity >= target]
        pool = big_enough or free
        best = min(abs(room.capacity - target) for room in pool)
        shortlist = [room for room in pool if abs(room.capacity - target) == best]
        return self.rng.choice(shortlist)


def build_sections(
    rng: random.Random,
    faculty: list[Faculty],
    classrooms: list[Classroom],
    departments: list[Department],
    courses: list[Course],
    section_terms: list[Term],
) -> list[Section]:
    scheduler = Scheduler(rng, faculty, classrooms, departments)
    terms_by_name = {term.name: term for term in section_terms}
    courses_by_dept_number = {
        (course.department_id, course.course_number): course for course in courses
    }
    courses_by_dept: dict[int, list[Course]] = defaultdict(list)
    for course in courses:
        courses_by_dept[course.department_id].append(course)

    def must(department: Department, number: int, term_name: str) -> None:
        course = courses_by_dept_number[(department.department_id, number)]
        if not scheduler.add(course, terms_by_name[term_name]):
            raise RuntimeError(
                f"could not schedule {department.code} {number} in {term_name}"
            )

    for department in departments:
        must(department, 101, "Spring 2026")
        must(department, 101, "Fall 2026")
    for department in departments:
        if department.name not in POPULAR:
            continue
        for term_name in ("Fall 2024", "Spring 2025", "Fall 2025", "Spring 2027"):
            must(department, 101, term_name)
        for term_name in ("Fall 2025", "Spring 2026", "Fall 2026", "Spring 2027"):
            must(department, 201, term_name)

    if len(scheduler.sections) != 560:
        raise RuntimeError(f"expected 560 guaranteed sections, got {len(scheduler.sections)}")

    weights = {101: 5, 110: 2, 201: 4, 301: 2, 401: 1}
    term_weights = [4 if term.season in {"Fall", "Spring"} else 1 for term in section_terms]
    guard = 0
    while len(scheduler.sections) < 800:
        guard += 1
        if guard > 50000:
            raise RuntimeError(f"stuck while scheduling at {len(scheduler.sections)} sections")
        department = rng.choice(departments)
        options = courses_by_dept[department.department_id]
        course = rng.choices(options, weights=[weights[item.course_number] for item in options], k=1)[0]
        term = rng.choices(section_terms, weights=term_weights, k=1)[0]
        scheduler.add(course, term)
    return scheduler.sections


def term_allowed(student: Student, term: Term) -> bool:
    if term.start_date < student.admit_term.start_date:
        return False
    if student.enrollment_status == "graduated":
        return term.end_date <= date(2026, 5, 15)
    if student.enrollment_status == "leave":
        return term.start_date < date(2026, 8, 1)
    if student.enrollment_status == "withdrawn":
        if student.withdrawal_term is None:
            return False
        return term.start_date <= student.withdrawal_term.start_date
    return True


def enrollment_status_for(rng: random.Random, student: Student, term: Term) -> str:
    if (
        student.enrollment_status == "withdrawn"
        and student.withdrawal_term is not None
        and term.term_id == student.withdrawal_term.term_id
    ):
        return "dropped"
    if term.end_date < AS_OF:
        return "dropped" if rng.random() < 0.08 else "completed"
    if term.start_date <= AS_OF:
        return "dropped" if rng.random() < 0.05 else "enrolled"
    return "enrolled"


def registration_date(rng: random.Random, student: Student, term: Term) -> date:
    enrolled = term.start_date - timedelta(days=rng.randint(10, 45))
    if enrolled > AS_OF:
        enrolled = AS_OF - timedelta(days=rng.randint(0, 14))
    if enrolled < student.admit_term.start_date:
        enrolled = student.admit_term.start_date
    return enrolled


def section_fits(
    student: Student,
    section: Section,
    term: Term,
    taken_courses: set[tuple[int, int]],
    schedules: dict[int, list[Section]],
    fill: dict[int, int],
) -> bool:
    if section.campus_name != student.campus_name:
        return False
    if not term_allowed(student, term):
        return False
    if (student.student_id, section.course_id) in taken_courses:
        return False
    if fill[section.section_id] >= section.capacity:
        return False
    for other in schedules[student.student_id]:
        if other.term_id != section.term_id:
            continue
        if times_conflict(
            other.meeting_days,
            other.start_time,
            other.end_time,
            section.meeting_days,
            section.start_time,
            section.end_time,
        ):
            return False
    return True


def build_enrollments(
    rng: random.Random,
    students: list[Student],
    sections: list[Section],
    terms: list[Term],
) -> list[Enrollment]:
    terms_by_id = {term.term_id: term for term in terms}
    by_campus_dept: dict[tuple[str, int], list[Section]] = defaultdict(list)
    by_campus: dict[str, list[Section]] = defaultdict(list)
    for section in sections:
        by_campus[section.campus_name].append(section)
        by_campus_dept[(section.campus_name, section.department_id)].append(section)

    enrollments: list[Enrollment] = []
    taken: set[tuple[int, int]] = set()
    schedules: dict[int, list[Section]] = defaultdict(list)
    fill: dict[int, int] = defaultdict(int)

    def place(student: Student, section: Section) -> None:
        term = terms_by_id[section.term_id]
        status = enrollment_status_for(rng, student, term)
        letter = None
        points = None
        if status == "completed":
            letter = rng.choice(GRADE_BAG)
            points = GRADE_POINTS[letter]
        enrollments.append(
            Enrollment(
                len(enrollments) + 1,
                student.student_id,
                section.section_id,
                registration_date(rng, student, term),
                status,
                letter,
                points,
            )
        )
        taken.add((student.student_id, section.course_id))
        schedules[student.student_id].append(section)
        fill[section.section_id] += 1

    ordered = list(students)
    rng.shuffle(ordered)

    def most_recent(section: Section) -> tuple:
        term = terms_by_id[section.term_id]
        return (-term.start_date.toordinal(), section.course_number)

    def try_place(student: Student, candidates: list[Section]) -> bool:
        if len(enrollments) >= 1000:
            return False
        for section in candidates:
            term = terms_by_id[section.term_id]
            if section_fits(student, section, term, taken, schedules, fill):
                place(student, section)
                return True
        return False

    # Prefer a finished term first so most continuing students have a grade,
    # then the in-progress term, then anything still open (including Spring 2027).
    for student in ordered:
        if len(enrollments) >= 600:
            break
        major = by_campus_dept[(student.campus_name, student.major_department_id)]
        ended = sorted(
            (section for section in major if terms_by_id[section.term_id].end_date < AS_OF),
            key=most_recent,
        )
        if try_place(student, ended):
            continue
        campus_ended = sorted(
            (
                section
                for section in by_campus[student.campus_name]
                if terms_by_id[section.term_id].end_date < AS_OF
            ),
            key=most_recent,
        )
        try_place(student, campus_ended)

    for student in ordered:
        if len(enrollments) >= 900:
            break
        major = by_campus_dept[(student.campus_name, student.major_department_id)]
        current = [
            section
            for section in major
            if terms_by_id[section.term_id].start_date <= AS_OF <= terms_by_id[section.term_id].end_date
        ]
        try_place(student, current)

    guard = 0
    while len(enrollments) < 1000:
        guard += 1
        if guard > 200000:
            raise RuntimeError(f"stuck while enrolling at {len(enrollments)} rows")
        student = rng.choice(students)
        if len(schedules[student.student_id]) >= 4:
            continue
        if rng.random() < 0.75:
            pool = by_campus_dept[(student.campus_name, student.major_department_id)]
        else:
            pool = by_campus[student.campus_name]
        if not pool:
            continue
        section = rng.choice(pool)
        term = terms_by_id[section.term_id]
        if section_fits(student, section, term, taken, schedules, fill):
            place(student, section)
    return enrollments


def build_advisors(
    rng: random.Random,
    students: list[Student],
    faculty: list[Faculty],
    terms: list[Term],
) -> list[AdvisorAssignment]:
    by_dept: dict[int, list[Faculty]] = defaultdict(list)
    for person in faculty:
        by_dept[person.department_id].append(person)
    ordered_terms = list(terms)
    assignments: list[AdvisorAssignment] = []
    next_id = 1

    eligible = []
    for student in students:
        options = [
            term
            for term in ordered_terms
            if term.start_date > student.admit_term.start_date and term.end_date < AS_OF
        ]
        # The successor of the chosen end term must exist.
        options = [term for index, term in enumerate(ordered_terms) if term in options and index + 1 < len(ordered_terms)]
        if options:
            eligible.append((student, options))
    rng.shuffle(eligible)
    history_for = {student.student_id: options for student, options in eligible[:100]}

    for student in students:
        advisors = by_dept[student.major_department_id]
        if student.student_id in history_for:
            end_term = rng.choice(history_for[student.student_id])
            end_index = next(index for index, term in enumerate(ordered_terms) if term.term_id == end_term.term_id)
            new_start = ordered_terms[end_index + 1]
            previous = rng.choice(advisors)
            current_pool = [person for person in advisors if person.faculty_id != previous.faculty_id] or advisors
            current = rng.choice(current_pool)
            assignments.append(
                AdvisorAssignment(
                    next_id,
                    student.student_id,
                    previous.faculty_id,
                    student.admit_term.term_id,
                    end_term.term_id,
                    0,
                )
            )
            next_id += 1
            assignments.append(
                AdvisorAssignment(
                    next_id,
                    student.student_id,
                    current.faculty_id,
                    new_start.term_id,
                    None,
                    1,
                )
            )
            next_id += 1
        else:
            current = rng.choice(advisors)
            assignments.append(
                AdvisorAssignment(
                    next_id,
                    student.student_id,
                    current.faculty_id,
                    student.admit_term.term_id,
                    None,
                    1,
                )
            )
            next_id += 1
    if len(assignments) != 900:
        raise RuntimeError(f"expected 900 advisor rows, got {len(assignments)}")
    return assignments


def insert_all(conn: sqlite3.Connection, table: str, columns: str, rows: list[tuple]) -> None:
    placeholders = ", ".join("?" for _ in columns.split(","))
    conn.executemany(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        rows,
    )


def write_database(
    terms: list[Term],
    buildings: list[Building],
    departments: list[Department],
    classrooms: list[Classroom],
    faculty: list[Faculty],
    students: list[Student],
    courses: list[Course],
    prerequisites: list[Prerequisite],
    requirements: list[Requirement],
    sections: list[Section],
    enrollments: list[Enrollment],
    advisors: list[AdvisorAssignment],
) -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    if AS_OF_DATE not in schema_text:
        raise RuntimeError("schema.sql is missing the as-of date from db/__init__.py")
    docs_path = SCHEMA_PATH.with_name("schema_docs.md")
    if docs_path.exists() and AS_OF_DATE not in docs_path.read_text(encoding="utf-8"):
        raise RuntimeError("schema_docs.md is missing the as-of date")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema_text)
        insert_all(
            conn,
            "terms",
            "term_id, name, season, academic_year, start_date, end_date",
            [term.row() for term in terms],
        )
        insert_all(
            conn,
            "buildings",
            "building_id, campus_name, name, code, city, state, year_built, floors",
            [row.row() for row in buildings],
        )
        insert_all(
            conn,
            "departments",
            "department_id, campus_name, name, code, office_building_id, office_phone",
            [row.row() for row in departments],
        )
        insert_all(
            conn,
            "classrooms",
            "classroom_id, building_id, room_number, capacity, room_type",
            [row.row() for row in classrooms],
        )
        insert_all(
            conn,
            "faculty",
            "faculty_id, department_id, first_name, last_name, email, academic_rank, hire_date, salary, office_building_id, office_room, is_department_chair",
            [row.row() for row in faculty],
        )
        insert_all(
            conn,
            "students",
            "student_id, first_name, last_name, email, ssn, date_of_birth, major_department_id, admit_term_id, enrollment_status, withdrawal_term_id, expected_grad_year, credits_earned, gpa",
            [row.row() for row in students],
        )
        insert_all(
            conn,
            "courses",
            "course_id, department_id, course_number, title, description, credits, course_level",
            [row.row() for row in courses],
        )
        insert_all(
            conn,
            "course_prerequisites",
            "course_id, prerequisite_course_id, minimum_grade",
            [row.row() for row in prerequisites],
        )
        insert_all(
            conn,
            "degree_requirements",
            "requirement_id, department_id, course_id, requirement_type",
            [row.row() for row in requirements],
        )
        insert_all(
            conn,
            "sections",
            "section_id, course_id, term_id, instructor_id, classroom_id, section_code, capacity, meeting_days, start_time, end_time",
            [row.row() for row in sections],
        )
        insert_all(
            conn,
            "enrollments",
            "enrollment_id, student_id, section_id, enrolled_on, status, letter_grade, grade_points",
            [row.row() for row in enrollments],
        )
        insert_all(
            conn,
            "advisor_assignments",
            "assignment_id, student_id, faculty_id, start_term_id, end_term_id, is_primary",
            [row.row() for row in advisors],
        )
        conn.execute(
            """
            UPDATE students
            SET gpa = (
                    SELECT ROUND(AVG(grade_points), 2)
                    FROM enrollments
                    WHERE enrollments.student_id = students.student_id
                      AND grade_points IS NOT NULL
                ),
                credits_earned = COALESCE((
                    SELECT SUM(courses.credits)
                    FROM enrollments
                    JOIN sections ON sections.section_id = enrollments.section_id
                    JOIN courses ON courses.course_id = sections.course_id
                    WHERE enrollments.student_id = students.student_id
                      AND enrollments.status = 'completed'
                      AND enrollments.grade_points >= 1.0
                ), 0)
            """
        )
        validate(conn, sections, enrollments)
        conn.commit()
        conn.execute("ANALYZE")
    except Exception:
        conn.rollback()
        conn.close()
        if DB_PATH.exists():
            DB_PATH.unlink()
        raise
    else:
        conn.close()


def assert_zero(conn: sqlite3.Connection, sql: str, message: str) -> None:
    count = conn.execute(sql).fetchone()[0]
    if count != 0:
        raise AssertionError(f"{message}: {count}")


def validate(conn: sqlite3.Connection, sections: list[Section], enrollments: list[Enrollment]) -> None:
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise AssertionError("foreign keys are off")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise AssertionError("foreign key check failed")
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise AssertionError("integrity check failed")

    for table, expected in EXPECTED_COUNTS.items():
        actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if actual != expected:
            raise AssertionError(f"{table} has {actual} rows, expected {expected}")
        if not 100 <= actual <= 1000:
            raise AssertionError(f"{table} is outside 100-1000 rows")

    current = [row[0] for row in conn.execute("SELECT name FROM current_term")]
    if current != ["Fall 2026"]:
        raise AssertionError(f"current_term view returned {current}")

    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM course_prerequisites p
        JOIN courses c ON c.course_id = p.course_id
        JOIN courses pre ON pre.course_id = p.prerequisite_course_id
        WHERE c.department_id <> pre.department_id
           OR pre.course_number >= c.course_number
        """,
        "invalid prerequisite",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM degree_requirements r
        JOIN courses c ON c.course_id = r.course_id
        JOIN departments course_dept ON course_dept.department_id = c.department_id
        JOIN departments major_dept ON major_dept.department_id = r.department_id
        WHERE course_dept.campus_name <> major_dept.campus_name
        """,
        "degree requirement crosses campuses",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM degree_requirements r
        JOIN courses c ON c.course_id = r.course_id
        WHERE r.requirement_type IN ('core', 'lab', 'elective')
          AND c.department_id <> r.department_id
        """,
        "major requirement owned by another department",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM degree_requirements r
        JOIN courses c ON c.course_id = r.course_id
        WHERE r.requirement_type = 'gened'
          AND c.department_id = r.department_id
        """,
        "gen-ed taught by the major department",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM sections s
        JOIN courses c ON c.course_id = s.course_id
        JOIN faculty f ON f.faculty_id = s.instructor_id
        WHERE f.department_id <> c.department_id
        """,
        "instructor from another department",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM sections s
        JOIN courses c ON c.course_id = s.course_id
        JOIN departments d ON d.department_id = c.department_id
        JOIN classrooms r ON r.classroom_id = s.classroom_id
        JOIN buildings b ON b.building_id = r.building_id
        WHERE b.campus_name <> d.campus_name
        """,
        "classroom on another campus",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM faculty f
        JOIN departments d ON d.department_id = f.department_id
        JOIN buildings b ON b.building_id = f.office_building_id
        WHERE b.campus_name <> d.campus_name
        """,
        "faculty office on another campus",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM advisor_assignments a
        JOIN students s ON s.student_id = a.student_id
        JOIN faculty f ON f.faculty_id = a.faculty_id
        WHERE s.major_department_id <> f.department_id
        """,
        "advisor outside the major",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM students s
        WHERE NOT EXISTS (
            SELECT 1 FROM advisor_assignments a
            WHERE a.student_id = s.student_id
              AND a.is_primary = 1
              AND a.end_term_id IS NULL
        )
        """,
        "student without an open primary advisor",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM departments d
        WHERE (
            SELECT COUNT(*) FROM faculty f
            WHERE f.department_id = d.department_id AND f.is_department_chair = 1
        ) <> 1
        """,
        "department chair count",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM enrollments e
        JOIN sections s ON s.section_id = e.section_id
        JOIN terms t ON t.term_id = s.term_id
        WHERE e.status = 'completed' AND t.end_date >= '2026-09-22'
        """,
        "completed enrollment in an unfinished term",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM enrollments e
        JOIN sections s ON s.section_id = e.section_id
        JOIN terms t ON t.term_id = s.term_id
        WHERE e.status = 'enrolled' AND t.end_date < '2026-09-22'
        """,
        "still enrolled in a finished term",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM enrollments e
        JOIN students st ON st.student_id = e.student_id
        JOIN sections s ON s.section_id = e.section_id
        JOIN terms sec_term ON sec_term.term_id = s.term_id
        JOIN terms admit ON admit.term_id = st.admit_term_id
        WHERE sec_term.start_date < admit.start_date
        """,
        "enrollment before admission",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM enrollments e
        WHERE e.enrolled_on > '2026-09-22'
        """,
        "registration dated after the snapshot",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*) FROM (
            SELECT s.section_id
            FROM sections s
            JOIN enrollments e ON e.section_id = s.section_id
            GROUP BY s.section_id
            HAVING COUNT(*) > s.capacity
        )
        """,
        "section over capacity",
    )
    assert_zero(
        conn,
        """
        SELECT COUNT(*)
        FROM departments d
        WHERE d.name = 'Computer Science'
          AND NOT EXISTS (
            SELECT 1
            FROM sections s
            JOIN courses c ON c.course_id = s.course_id
            JOIN terms t ON t.term_id = s.term_id
            WHERE c.department_id = d.department_id
              AND c.course_number = 101
              AND t.name = 'Fall 2026'
          )
        """,
        "missing Fall 2026 introductory programming section",
    )

    for letter, points in conn.execute(
        "SELECT letter_grade, grade_points FROM enrollments WHERE letter_grade IS NOT NULL"
    ):
        if abs(points - GRADE_POINTS[letter]) > 1e-9:
            raise AssertionError(f"grade map mismatch for {letter}")

    bad_gpa = conn.execute(
        "SELECT COUNT(*) FROM students WHERE gpa IS NOT NULL AND (gpa < 0 OR gpa > 4)"
    ).fetchone()[0]
    if bad_gpa:
        raise AssertionError("gpa out of range")

    by_term: dict[int, list[Section]] = defaultdict(list)
    for section in sections:
        by_term[section.term_id].append(section)
    for group in by_term.values():
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                clash = times_conflict(
                    left.meeting_days,
                    left.start_time,
                    left.end_time,
                    right.meeting_days,
                    right.start_time,
                    right.end_time,
                )
                if clash and left.instructor_id == right.instructor_id:
                    raise AssertionError("instructor double-booked")
                if clash and left.classroom_id == right.classroom_id:
                    raise AssertionError("classroom double-booked")

    sections_by_id = {section.section_id: section for section in sections}
    by_student_term: dict[tuple[int, int], list[Section]] = defaultdict(list)
    seen_courses: set[tuple[int, int]] = set()
    for enrollment in enrollments:
        section = sections_by_id[enrollment.section_id]
        key = (enrollment.student_id, section.course_id)
        if key in seen_courses:
            raise AssertionError("student enrolled in the same course twice")
        seen_courses.add(key)
        by_student_term[(enrollment.student_id, section.term_id)].append(section)
    for group in by_student_term.values():
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                if times_conflict(
                    left.meeting_days,
                    left.start_time,
                    left.end_time,
                    right.meeting_days,
                    right.start_time,
                    right.end_time,
                ):
                    raise AssertionError("student time conflict")


def print_summary(conn_path: Path) -> None:
    conn = sqlite3.connect(conn_path)
    try:
        print(f"{UNIVERSITY_NAME}")
        print(f"Database: {conn_path}")
        print(f"Seed: {SEED}")
        print(f"As-of date: {AS_OF_DATE} (current term: Fall 2026)")
        print()
        print(f"{'table':<24} {'rows':>6}")
        for table in EXPECTED_COUNTS:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table:<24} {count:>6}")
        salary_min, salary_max = conn.execute("SELECT MIN(salary), MAX(salary) FROM faculty").fetchone()
        ssn_count = conn.execute("SELECT COUNT(*) FROM students WHERE ssn LIKE '9%'").fetchone()[0]
        print()
        print(f"Sensitive columns populated: students.ssn ({ssn_count}), faculty.salary")
        print(f"Faculty salary range: ${salary_min:,} - ${salary_max:,}")
        print()
        print("Enrollment status")
        for status, count in conn.execute(
            "SELECT enrollment_status, COUNT(*) FROM students GROUP BY enrollment_status ORDER BY 1"
        ):
            print(f"  {status:<12} {count}")
        print()
        print("Fall 2026 enrollments by status")
        for status, count in conn.execute(
            """
            SELECT e.status, COUNT(*)
            FROM enrollments e
            JOIN sections s ON s.section_id = e.section_id
            JOIN terms t ON t.term_id = s.term_id
            WHERE t.name = 'Fall 2026'
            GROUP BY e.status
            ORDER BY 1
            """
        ):
            print(f"  {status:<12} {count}")
    finally:
        conn.close()


def main() -> None:
    rng = random.Random(SEED)
    terms = build_terms()
    section_terms = [
        term for term in terms if SECTION_WINDOW_START <= term.start_date <= SECTION_WINDOW_END
    ]
    if len(section_terms) != 15:
        raise RuntimeError(f"expected 15 section terms, got {len(section_terms)}")
    buildings, departments, classrooms = build_places()
    faculty = build_faculty(rng, departments)
    students = build_students(rng, departments, terms, section_terms)
    courses, prerequisites, requirements = build_catalog(departments)
    sections = build_sections(rng, faculty, classrooms, departments, courses, section_terms)
    enrollments = build_enrollments(rng, students, sections, terms)
    advisors = build_advisors(rng, students, faculty, terms)
    write_database(
        terms,
        buildings,
        departments,
        classrooms,
        faculty,
        students,
        courses,
        prerequisites,
        requirements,
        sections,
        enrollments,
        advisors,
    )
    print_summary(DB_PATH)


if __name__ == "__main__":
    main()
