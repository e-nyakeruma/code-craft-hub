"""
CodeCraftHub - Course REST API

This Flask application provides CRUD operations for courses and stores
the course data in a local JSON file named "courses.json".

Run the application with:

    python app.py
"""

from datetime import datetime
import json
from pathlib import Path

from flask import Flask, jsonify, request


# -----------------------------------------------------------------------------
# Flask application setup
# -----------------------------------------------------------------------------

app = Flask(__name__)

# Store courses.json in the same directory as this Python file.
DATA_FILE = Path(__file__).parent / "courses.json"

# These are the only statuses allowed for a course.
VALID_STATUSES = {
    "Not Started",
    "In Progress",
    "Completed",
}


# -----------------------------------------------------------------------------
# Custom exception for file-related errors
# -----------------------------------------------------------------------------

class StorageError(Exception):
    """Raised when courses.json cannot be read or written."""


# -----------------------------------------------------------------------------
# JSON file helper functions
# -----------------------------------------------------------------------------

def ensure_data_file():
    """
    Create courses.json automatically if it does not already exist.

    The file starts with an empty JSON list because courses will be stored
    as a list of course objects.
    """
    try:
        if not DATA_FILE.exists():
            with open(DATA_FILE, "w", encoding="utf-8") as file:
                json.dump([], file, indent=4)
    except OSError as error:
        raise StorageError(
            f"Unable to create data file: {error}"
        ) from error


def load_courses():
    """
    Read and return all courses from courses.json.

    Returns:
        list: A list of course dictionaries.

    Raises:
        StorageError: If the file cannot be read or contains invalid JSON.
    """
    ensure_data_file()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            courses = json.load(file)

        # Make sure the JSON file contains a list.
        if not isinstance(courses, list):
            raise StorageError(
                "courses.json must contain a JSON list."
            )

        return courses

    except json.JSONDecodeError as error:
        raise StorageError(
            f"courses.json contains invalid JSON: {error}"
        ) from error

    except OSError as error:
        raise StorageError(
            f"Unable to read courses.json: {error}"
        ) from error


def save_courses(courses):
    """
    Save the supplied list of courses to courses.json.

    Args:
        courses (list): The course data to save.

    Raises:
        StorageError: If the file cannot be written.
    """
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(courses, file, indent=4)
    except OSError as error:
        raise StorageError(
            f"Unable to write to courses.json: {error}"
        ) from error


# -----------------------------------------------------------------------------
# Validation helper functions
# -----------------------------------------------------------------------------

def validate_date(date_value):
    """
    Validate that a date uses the exact YYYY-MM-DD format.

    Args:
        date_value: The value received from the request.

    Returns:
        str or None: An error message, or None if the date is valid.
    """
    if not isinstance(date_value, str):
        return "target_date must be a string in YYYY-MM-DD format."

    try:
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d")

        # This extra check rejects values such as 2026-1-1.
        if parsed_date.strftime("%Y-%m-%d") != date_value:
            return "target_date must use the format YYYY-MM-DD."

    except ValueError:
        return "target_date must use the format YYYY-MM-DD."

    return None


def validate_course_data(data, require_all_fields=True):
    """
    Validate fields received when creating or updating a course.

    Args:
        data (dict): JSON data from the request.
        require_all_fields (bool): Whether every required field is needed.

    Returns:
        str or None: An error message, or None if the data is valid.
    """
    if not isinstance(data, dict):
        return "Request body must contain a JSON object."

    required_fields = [
        "name",
        "description",
        "target_date",
        "status",
    ]

    # For POST and PUT, all required fields must be supplied.
    if require_all_fields:
        missing_fields = [
            field
            for field in required_fields
            if field not in data
            or data[field] is None
            or (
                isinstance(data[field], str)
                and not data[field].strip()
            )
        ]

        if missing_fields:
            return {
                "message": "Missing required fields.",
                "fields": missing_fields,
            }

    # Validate the status if it was supplied.
    if "status" in data:
        if data["status"] not in VALID_STATUSES:
            return {
                "message": "Invalid status value.",
                "allowed_statuses": sorted(VALID_STATUSES),
            }

    # Validate the target date if it was supplied.
    if "target_date" in data:
        date_error = validate_date(data["target_date"])

        if date_error:
            return date_error

    return None


def find_course(courses, course_id):
    """
    Find one course by its ID.

    Returns:
        dict or None: The matching course, if found.
    """
    return next(
        (course for course in courses if course.get("id") == course_id),
        None,
    )


def get_next_course_id(courses):
    """
    Generate the next course ID.

    IDs begin at 1. The next ID is one greater than the current
    highest ID. If there are no courses, the next ID is 1.
    """
    if not courses:
        return 1

    return max(course["id"] for course in courses) + 1


def get_current_timestamp():
    """
    Return an automatically generated UTC timestamp.

    Example:
        2026-08-20T14:30:00.123456+00:00
    """
    return datetime.now().astimezone().isoformat()


# -----------------------------------------------------------------------------
# API endpoints
# -----------------------------------------------------------------------------

@app.route("/api/courses", methods=["POST"])
def create_course():
    """
    Add a new course.

    POST /api/courses
    """
    data = request.get_json(silent=True)

    validation_error = validate_course_data(data)

    if validation_error:
        if isinstance(validation_error, dict):
            return jsonify({"error": validation_error}), 400

        return jsonify({"error": validation_error}), 400

    try:
        courses = load_courses()

        new_course = {
            "id": get_next_course_id(courses),
            "name": data["name"].strip(),
            "description": data["description"].strip(),
            "target_date": data["target_date"],
            "status": data["status"],
            "created_at": get_current_timestamp(),
        }

        courses.append(new_course)
        save_courses(courses)

        return jsonify(new_course), 201

    except StorageError as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/courses", methods=["GET"])
def get_all_courses():
    """
    Return all courses.

    GET /api/courses
    """
    try:
        courses = load_courses()
        return jsonify(courses), 200

    except StorageError as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_single_course(course_id):
    """
    Return one course by ID.

    GET /api/courses/<course_id>
    """
    try:
        courses = load_courses()
        course = find_course(courses, course_id)

        if course is None:
            return jsonify({
                "error": f"Course with ID {course_id} was not found."
            }), 404

        return jsonify(course), 200

    except StorageError as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/courses/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    """
    Update an existing course.

    PUT /api/courses/<course_id>

    PUT requires all course fields except id and created_at.
    The original id and created_at values are preserved.
    """
    data = request.get_json(silent=True)

    validation_error = validate_course_data(data)

    if validation_error:
        if isinstance(validation_error, dict):
            return jsonify({"error": validation_error}), 400

        return jsonify({"error": validation_error}), 400

    try:
        courses = load_courses()
        course = find_course(courses, course_id)

        if course is None:
            return jsonify({
                "error": f"Course with ID {course_id} was not found."
            }), 404

        # Update only the editable fields.
        course["name"] = data["name"].strip()
        course["description"] = data["description"].strip()
        course["target_date"] = data["target_date"]
        course["status"] = data["status"]

        save_courses(courses)

        return jsonify(course), 200

    except StorageError as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/courses/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    """
    Delete a course by ID.

    DELETE /api/courses/<course_id>
    """
    try:
        courses = load_courses()
        course = find_course(courses, course_id)

        if course is None:
            return jsonify({
                "error": f"Course with ID {course_id} was not found."
            }), 404

        courses.remove(course)
        save_courses(courses)

        return jsonify({
            "message": f"Course with ID {course_id} was deleted successfully."
        }), 200

    except StorageError as error:
        return jsonify({"error": str(error)}), 500


# -----------------------------------------------------------------------------
# Common error handlers
# -----------------------------------------------------------------------------

@app.errorhandler(404)
def handle_not_found(error):
    """Return JSON instead of Flask's default HTML 404 page."""
    return jsonify({
        "error": "The requested endpoint was not found."
    }), 404


@app.errorhandler(405)
def handle_method_not_allowed(error):
    """Return JSON when an unsupported HTTP method is used."""
    return jsonify({
        "error": "The HTTP method is not allowed for this endpoint."
    }), 405


@app.errorhandler(500)
def handle_internal_server_error(error):
    """Return a simple JSON response for unexpected server errors."""
    return jsonify({
        "error": "An unexpected internal server error occurred."
    }), 500

# -----------------------------------------------------------------------------
# Application startup
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Create courses.json before starting the development server.
    # If the file cannot be created, display the problem and stop the app.
    try:
        ensure_data_file()
        print(f"Using course data file: {DATA_FILE}")
    except StorageError as error:
        print(f"Startup error: {error}")
        raise SystemExit(1)

    app.run(debug=True)