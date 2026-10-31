"""Seeded sample data: a campus of students grouped around interest themes."""
import random

from graph_engine import Student

DEFAULT_THRESHOLD = 0.3

THEMES = {
    "ai": ["machine learning", "python", "data science", "deep learning", "kaggle", "statistics"],
    "web": ["web development", "react", "ui design", "open source", "javascript", "startups"],
    "music": ["guitar", "singing", "music production", "indie bands", "classical music", "djing"],
    "sports": ["cricket", "football", "badminton", "gym", "running", "yoga"],
    "arts": ["painting", "photography", "sketching", "film making", "poetry", "calligraphy"],
    "gaming": ["esports", "game development", "chess", "board games", "anime", "streaming"],
    "robotics": ["robotics", "arduino", "drones", "3d printing", "iot", "electronics"],
    "finance": ["investing", "stock markets", "economics", "entrepreneurship", "cryptocurrency", "public speaking"],
}

DEPARTMENTS = {
    "ai": ["Computer Science", "Mathematics", "Statistics"],
    "web": ["Computer Science", "Information Technology", "Design"],
    "music": ["Fine Arts", "Literature", "Computer Science"],
    "sports": ["Mechanical", "Civil", "Management"],
    "arts": ["Design", "Fine Arts", "Literature"],
    "gaming": ["Computer Science", "Information Technology", "Design"],
    "robotics": ["Electronics", "Mechanical", "Computer Science"],
    "finance": ["Management", "Economics", "Commerce"],
}

NAMES = [
    "Aarav Sharma", "Ananya Iyer", "Vihaan Patel", "Diya Nair", "Arjun Reddy", "Isha Kapoor",
    "Kabir Singh", "Meera Joshi", "Rohan Gupta", "Saanvi Menon", "Aditya Verma", "Kavya Rao",
    "Yash Malhotra", "Riya Bansal", "Dev Mehta", "Tara Choudhury", "Neil Fernandes", "Pooja Desai",
    "Harsh Agarwal", "Simran Kaur", "Ishaan Bose", "Nisha Pillai", "Karan Thakur", "Aditi Mishra",
    "Varun Saxena", "Prerna Jain", "Siddharth Rane", "Lakshmi Krishnan", "Manav Chawla", "Zoya Khan",
    "Tanmay Kulkarni", "Anjali Dubey", "Rahul Pandey", "Sneha Ghosh", "Pranav Nambiar", "Ritika Sethi",
    "Aman Tiwari", "Devika Shetty", "Nikhil Bhatt", "Shreya Das", "Om Prakash Yadav", "Mitali Sinha",
    "Farhan Qureshi", "Bhavna Soni", "Jay Parekh", "Kritika Arora", "Samar Hussain", "Palak Goyal",
]


def generate_students(seed: int = 7):
    rng = random.Random(seed)
    themes = list(THEMES)
    students = []
    for i, name in enumerate(NAMES, start=1):
        primary = themes[(i - 1) % len(themes)]
        interests = set(rng.sample(THEMES[primary], 4))
        dept = rng.choice(DEPARTMENTS[primary])

        if i % 11 == 0:
            # connector: half in one theme, half in another, links two communities
            other = rng.choice([t for t in themes if t != primary])
            interests = set(rng.sample(THEMES[primary], 3)) | set(rng.sample(THEMES[other], 3))
        elif rng.random() < 0.3:
            other = rng.choice([t for t in themes if t != primary])
            interests.add(rng.choice(THEMES[other]))

        students.append(Student(i, name, dept, rng.randint(1, 4), frozenset(interests)))
    return students
