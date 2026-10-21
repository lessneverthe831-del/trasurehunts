"""Stage 1: 5-Question Quiz Definitions
"""

QUESTIONS = [
    {
        "id": 1,
        "question": "What is the primary function of a cryptographic hash function in digital security?",
        "options": [
            {"id": "A", "text": "Reversible two-way encryption of confidential messages"},
            {"id": "B", "text": "Generating a unique, fixed-length digital fingerprint of data"},
            {"id": "C", "text": "Lossless compression of large multi-media files"},
            {"id": "D", "text": "Dynamically assigning private IP addresses across a LAN"}
        ],
        "correct_answer": "B"
    },
    {
        "id": 2,
        "question": "In computer networking, what does DNS stand for and what is its primary role?",
        "options": [
            {"id": "A", "text": "Domain Name System: Translates human-readable domain names into IP addresses"},
            {"id": "B", "text": "Dynamic Network Standard: Determines the shortest physical fiber optic path"},
            {"id": "C", "text": "Digital Node Socket: Manages asynchronous TLS handshake protocols"},
            {"id": "D", "text": "Data Navigation Stream: Tracks user browser cookies across proxy hops"}
        ],
        "correct_answer": "A"
    },
    {
        "id": 3,
        "question": "If an 8-bit binary register stores the sequence 10110010, what is its decimal value?",
        "options": [
            {"id": "A", "text": "168"},
            {"id": "B", "text": "178"},
            {"id": "C", "text": "192"},
            {"id": "D", "text": "154"}
        ],
        "correct_answer": "B"
    },
    {
        "id": 4,
        "question": "Which HTTP status code explicitly signifies that a new resource has been successfully created on the server?",
        "options": [
            {"id": "A", "text": "200 OK"},
            {"id": "B", "text": "201 Created"},
            {"id": "C", "text": "204 No Content"},
            {"id": "D", "text": "301 Moved Permanently"}
        ],
        "correct_answer": "B"
    },
    {
        "id": 5,
        "question": "Using a classical Caesar cipher with a key shift of +3, what does the plaintext string 'CYBER' encrypt to?",
        "options": [
            {"id": "A", "text": "FBEHU"},
            {"id": "B", "text": "DZEFS"},
            {"id": "C", "text": "EZFGT"},
            {"id": "D", "text": "GAFIU"}
        ],
        "correct_answer": "A"
    }
]


def verify_quiz_answers(user_answers: dict) -> tuple[bool, str]:
    """
    Verifies user answers against correct answers.
    Returns (is_all_correct, failure_reason).
    """
    for q in QUESTIONS:
        qid_str = str(q["id"])
        submitted = user_answers.get(qid_str)
        if not submitted:
            return False, f"Question {q['id']} was not answered."
        if submitted.strip().upper() != q["correct_answer"]:
            return False, f"Incorrect answer on Question {q['id']}."
    return True, "All answers correct."
